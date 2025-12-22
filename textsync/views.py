import structlog
from datetime import timedelta

from django.contrib.auth import authenticate
from django.core.cache import cache
from django.db import connection
from django.db.models import Q, Count
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.conf import settings
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes, action
from rest_framework.exceptions import ParseError, PermissionDenied
from rest_framework.response import Response

from .models import Shortcut, ShortcutSet, ExpiringToken, ShortcutUsageLog
from .serializers import ShortcutSerializer, ShortcutSetSerializer
from .cache import get_user_shortcuts_key, get_user_sets_key
from .throttling import (
    LoginRateThrottle, TokenRefreshRateThrottle, BulkSyncRateThrottle
)

logger = structlog.get_logger(__name__)


class ShortcutSetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for listing available shortcut sets.
    Read-only - sets are managed via Django admin.
    Staff users see only their own sets + sets shared with them.
    Superusers see all sets.

    Caching: Results are cached per-user for 10 minutes.
    """
    serializer_class = ShortcutSetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """Override list to add caching."""
        cache_key = get_user_sets_key(request.user.id)
        cached_response = cache.get(cache_key)

        if cached_response is not None:
            logger.debug(f"Cache hit for sets: user={request.user.id}")
            return Response(cached_response)

        response = super().list(request, *args, **kwargs)

        if response.status_code == 200:
            timeout = getattr(settings, 'CACHE_TIMEOUTS', {}).get('shortcut_sets', 600)
            cache.set(cache_key, response.data, timeout)
            logger.debug(f"Cache set for sets: user={request.user.id}")

        return response

    def get_queryset(self):
        user = self.request.user
        base_qs = ShortcutSet.objects.select_related("owner")
        base_qs = base_qs.prefetch_related("visible_to")
        base_qs = base_qs.annotate(shortcut_count=Count("shortcuts", distinct=True))
        if user.is_superuser:
            # Superusers see all sets
            return base_qs.order_by('set_type', 'name')

        # Business rule:
        # - General sets: visible to everyone (no filter)
        # - Personal sets: visible only to owner
        return base_qs.filter(
            Q(set_type='general') | Q(owner=user) | Q(visible_to=user)
        ).distinct().order_by('set_type', 'name')


class ShortcutViewSet(viewsets.ModelViewSet):
    """
    API endpoint for shortcuts with full CRUD support.
    - GET /api/shortcuts/ - List shortcuts from accessible sets
    - GET /api/shortcuts/?search=query - Search shortcuts
    - GET /api/shortcuts/my/ - List user's own shortcuts
    - POST /api/shortcuts/ - Create (only in user's personal sets)
    - PUT /api/shortcuts/{id}/ - Update (only own shortcuts)
    - DELETE /api/shortcuts/{id}/ - Delete (only own shortcuts)

    Security: Only returns shortcuts that the authenticated user has access to.
    CRUD: Users can only manage shortcuts they own in their personal sets.
    Caching: Full list results are cached for 5 minutes. Delta sync bypasses cache.
    """
    serializer_class = ShortcutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """Override list to add caching (only for full sync, not delta)."""
        updated_after = request.query_params.get('updated_after')
        sets_param = request.query_params.get('sets', '')

        # Only cache full syncs without filters
        if updated_after:
            # Delta sync - don't cache partial results
            return super().list(request, *args, **kwargs)

        cache_key = f"{get_user_shortcuts_key(request.user.id)}:{sets_param}"
        cached_response = cache.get(cache_key)

        if cached_response is not None:
            logger.debug(f"Cache hit for shortcuts: user={request.user.id}")
            return Response(cached_response)

        response = super().list(request, *args, **kwargs)

        if response.status_code == 200:
            timeout = getattr(settings, 'CACHE_TIMEOUTS', {}).get('shortcuts', 300)
            cache.set(cache_key, response.data, timeout)
            logger.debug(f"Cache set for shortcuts: user={request.user.id}")

        return response

    def get_queryset(self):
        user = self.request.user
        queryset = Shortcut.objects.select_related('owner', 'updated_by')
        queryset = queryset.prefetch_related('sets').order_by("key")

        # Get sets that user has access to (same logic as ShortcutSetViewSet)
        if user.is_superuser:
            accessible_sets = ShortcutSet.objects.all()
        else:
            # User can access: general sets + their own personal sets
            accessible_sets = ShortcutSet.objects.filter(
                Q(set_type='general') | Q(owner=user) | Q(visible_to=user)
            ).distinct()

        # Filter by sets parameter (if provided)
        sets_param = self.request.query_params.get('sets', None)

        if sets_param:
            # User specified which sets they want
            requested_set_names = {
                s.strip().lower() for s in sets_param.split(',') if s.strip()
            }

            if not requested_set_names:
                return queryset.none()

            # Validate: user can only request sets they have access to
            # Build Q filter for case-insensitive matching
            q_filters = Q()
            for name in requested_set_names:
                q_filters |= Q(name__iexact=name)

            requested_sets = accessible_sets.filter(q_filters)

            requested_set_names_found = set(
                name.lower() for name in requested_sets.values_list('name', flat=True)
            )

            # Security: if user requested inaccessible sets, return empty
            if requested_set_names_found != requested_set_names:
                # Some requested sets don't exist or user doesn't have access
                return queryset.none()

            # Return shortcuts from the validated requested sets
            queryset = queryset.filter(sets__in=requested_sets).distinct()
        else:
            # No sets param provided: return shortcuts from ALL accessible sets
            # This prevents exposing all shortcuts - only those in accessible sets
            queryset = queryset.filter(sets__in=accessible_sets).distinct()

        # Delta sync: filter by updated_after timestamp
        updated_after = self.request.query_params.get('updated_after', None)
        if updated_after:
            parsed_updated_after = parse_datetime(updated_after.replace('Z', '+00:00'))
            if not parsed_updated_after:
                raise ParseError("updated_after must be a valid ISO 8601 datetime")

            if timezone.is_naive(parsed_updated_after):
                tz = timezone.get_current_timezone()
                parsed_updated_after = timezone.make_aware(parsed_updated_after, tz)

            queryset = queryset.filter(updated_at__gt=parsed_updated_after)

        # Support search parameter
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(key__icontains=search) | Q(value__icontains=search)
            )

        return queryset

    @action(detail=False, methods=['get'])
    def my(self, request):
        """
        GET /api/shortcuts/my/
        Returns only shortcuts owned by the current user.
        """
        import logging
        logger = logging.getLogger(__name__)
        try:
            queryset = Shortcut.objects.filter(owner=request.user).prefetch_related('sets')
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.exception(f"Error in /shortcuts/my/ for user {request.user}: {e}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        """
        POST /api/shortcuts/
        Create a new shortcut owned by the current user.
        Only allows adding to personal sets owned by the user.
        """
        user = request.user
        data = request.data.copy()

        # Validate sets - user can only add to their own personal sets
        set_ids = data.get('sets', [])
        if set_ids:
            allowed_sets = ShortcutSet.objects.filter(
                id__in=set_ids,
                set_type='personal',
                owner=user
            )
            if allowed_sets.count() != len(set_ids):
                raise PermissionDenied("You can only add shortcuts to your own personal sets.")

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=user, updated_by=user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """
        PUT /api/shortcuts/{id}/
        Update a shortcut. Only the owner can update their shortcuts.
        """
        instance = self.get_object()
        user = request.user

        if instance.owner != user and not user.is_superuser:
            raise PermissionDenied("You can only edit your own shortcuts.")

        data = request.data.copy()

        # Validate sets - user can only use their own personal sets
        set_ids = data.get('sets', [])
        if set_ids:
            allowed_sets = ShortcutSet.objects.filter(
                id__in=set_ids,
                set_type='personal',
                owner=user
            )
            if allowed_sets.count() != len(set_ids):
                raise PermissionDenied("You can only add shortcuts to your own personal sets.")

        serializer = self.get_serializer(instance, data=data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=user)

        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        DELETE /api/shortcuts/{id}/
        Delete a shortcut. Only the owner can delete their shortcuts.
        """
        instance = self.get_object()
        user = request.user

        if instance.owner != user and not user.is_superuser:
            raise PermissionDenied("You can only delete your own shortcuts.")

        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([LoginRateThrottle])
def login_view(request):
    """
    Login endpoint. Returns auth token on success.

    POST /api/auth/login/
    Body: { "username": "user", "password": "pass" }
    Returns: { "token": "abc123...", "expires_at": "2025-04-30T...", "user": {...} }

    Rate limited: 10 requests per minute per IP to prevent brute force.
    """
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response(
            {'error': 'Username and password required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = authenticate(username=username, password=password)

    if user is None:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.is_active:
        return Response(
            {'error': 'User account is disabled'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Get or create token for user
    token, created = ExpiringToken.objects.get_or_create(user=user)

    # If token exists but is expired, regenerate it
    if not created and token.is_expired():
        token.delete()
        token = ExpiringToken.objects.create(user=user)

    return Response({
        'token': token.key,
        'expires_at': token.expires_at.isoformat(),
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
        }
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """
    Logout endpoint. Deletes the user's token.

    POST /api/auth/logout/
    Headers: Authorization: Token abc123...
    """
    try:
        # Delete the user's token
        request.user.auth_token.delete()
        return Response({'message': 'Successfully logged out'})
    except ExpiringToken.DoesNotExist:
        return Response({'message': 'No active session'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def verify_token_view(request):
    """
    Verify if token is still valid.

    GET /api/auth/verify/
    Headers: Authorization: Token abc123...
    Returns: { "valid": true, "user": {...}, "expires_at": "..." }
    """
    token = request.user.auth_token

    return Response({
        'valid': not token.is_expired(),
        'expires_at': token.expires_at.isoformat(),
        'user': {
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
        }
    })


def privacy_view(request):
    """
    Privacy Policy page for Chrome Web Store compliance.
    """
    return render(request, 'privacy.html')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([TokenRefreshRateThrottle])
def refresh_token_view(request):
    """
    Refresh the user's authentication token.

    POST /api/auth/refresh/
    Headers: Authorization: Token abc123...
    Returns: { "token": "new_token...", "expires_at": "...", "user": {...} }

    Security: Only refreshes if token is within 30 days of expiration.
    This prevents unnecessary token churn while ensuring smooth UX.
    Rate limited: 5 requests per hour per user.
    """
    try:
        old_token = request.user.auth_token
    except ExpiringToken.DoesNotExist:
        return Response(
            {'error': 'No active token found'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check if token is within refresh window (30 days before expiration)
    refresh_window = timedelta(days=30)
    time_until_expiry = old_token.expires_at - timezone.now()

    if time_until_expiry > refresh_window:
        # Token is still fresh, no need to refresh
        logger.info(f"Token refresh rejected - too early: user={request.user.id}")
        return Response({
            'message': 'Token still valid, refresh not needed',
            'token': old_token.key,
            'expires_at': old_token.expires_at.isoformat(),
            'days_until_expiry': time_until_expiry.days,
        })

    # Delete old token and create new one
    old_token.delete()
    new_token = ExpiringToken.objects.create(user=request.user)

    logger.info(f"Token refreshed: user={request.user.id}")

    return Response({
        'token': new_token.key,
        'expires_at': new_token.expires_at.isoformat(),
        'user': {
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
        }
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([BulkSyncRateThrottle])
def bulk_sync_view(request):
    """
    Bulk sync endpoint - returns both sets and shortcuts in a single request.

    POST /api/sync/bulk/
    Body: { "sets": ["set1", "set2"], "updated_after": "..." (optional) }
    Returns: { "sets": [...], "shortcuts": [...], "server_time": "..." }

    This reduces the number of API calls from 2 to 1, improving performance.
    Rate limited: 60 requests per hour per user (heavy operation).
    """
    user = request.user
    requested_sets = request.data.get('sets', [])
    updated_after = request.data.get('updated_after')

    # Build cache key
    sets_key = ",".join(sorted(requested_sets)) if requested_sets else "all"
    cache_key = f"bulk_sync:{user.id}:{sets_key}"

    # Only use cache for full sync (no updated_after)
    if not updated_after:
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            logger.debug(f"Cache hit for bulk sync: user={user.id}")
            return Response(cached_response)

    # Get accessible sets
    if user.is_superuser:
        accessible_sets = ShortcutSet.objects.all()
    else:
        accessible_sets = ShortcutSet.objects.filter(
            Q(set_type='general') | Q(owner=user) | Q(visible_to=user)
        ).distinct()

    # Filter by requested sets if provided
    if requested_sets:
        q_filters = Q()
        for name in requested_sets:
            q_filters |= Q(name__iexact=name.strip())
        accessible_sets = accessible_sets.filter(q_filters)

    # Serialize sets with shortcut count
    sets_qs = accessible_sets.select_related("owner").prefetch_related("visible_to")
    sets_qs = sets_qs.annotate(shortcut_count=Count("shortcuts", distinct=True))
    sets_data = ShortcutSetSerializer(sets_qs, many=True).data

    # Get shortcuts from accessible sets
    shortcuts_qs = Shortcut.objects.filter(sets__in=accessible_sets).distinct()
    shortcuts_qs = shortcuts_qs.select_related('owner', 'updated_by')
    shortcuts_qs = shortcuts_qs.prefetch_related('sets')
    shortcuts_qs = shortcuts_qs.order_by("key")

    # Apply delta sync filter
    if updated_after:
        parsed_updated_after = parse_datetime(updated_after.replace('Z', '+00:00'))
        if parsed_updated_after:
            if timezone.is_naive(parsed_updated_after):
                tz = timezone.get_current_timezone()
                parsed_updated_after = timezone.make_aware(parsed_updated_after, tz)
            shortcuts_qs = shortcuts_qs.filter(updated_at__gt=parsed_updated_after)

    shortcuts_data = ShortcutSerializer(shortcuts_qs, many=True).data

    response_data = {
        'sets': sets_data,
        'shortcuts': shortcuts_data,
        'server_time': timezone.now().isoformat(),
        'count': {
            'sets': len(sets_data),
            'shortcuts': len(shortcuts_data),
        }
    }

    # Cache full sync results
    if not updated_after:
        timeout = getattr(settings, 'CACHE_TIMEOUTS', {}).get('shortcuts', 300)
        cache.set(cache_key, response_data, timeout)
        logger.debug(f"Cache set for bulk sync: user={user.id}")

    logger.info(
        f"Bulk sync: user={user.id}, sets={len(sets_data)}, "
        f"shortcuts={len(shortcuts_data)}"
    )

    return Response(response_data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check_view(request):
    """
    Health check endpoint for monitoring and load balancers.

    GET /api/health/
    Returns: {
        "status": "healthy" | "degraded" | "unhealthy",
        "version": "1.0.0",
        "timestamp": "...",
        "checks": {
            "database": { "status": "ok", "latency_ms": 5 },
            "cache": { "status": "ok", "latency_ms": 2 }
        }
    }

    No authentication required - this endpoint is meant for:
    - Kubernetes liveness/readiness probes
    - Load balancer health checks
    - Monitoring systems (Prometheus, Datadog, etc.)
    """
    import time
    from django.conf import settings as django_settings

    checks = {}
    overall_status = "healthy"

    # Check database connectivity
    db_start = time.time()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_latency = (time.time() - db_start) * 1000
        checks['database'] = {
            'status': 'ok',
            'latency_ms': round(db_latency, 2)
        }
    except Exception as e:
        checks['database'] = {
            'status': 'error',
            'error': str(e)
        }
        overall_status = "unhealthy"
        logger.error(f"Health check - database error: {e}")

    # Check cache connectivity
    cache_start = time.time()
    try:
        test_key = "health_check_test"
        cache.set(test_key, "ok", timeout=10)
        result = cache.get(test_key)
        cache.delete(test_key)
        cache_latency = (time.time() - cache_start) * 1000

        if result == "ok":
            checks['cache'] = {
                'status': 'ok',
                'latency_ms': round(cache_latency, 2)
            }
        else:
            checks['cache'] = {
                'status': 'degraded',
                'error': 'Cache read/write failed'
            }
            if overall_status == "healthy":
                overall_status = "degraded"
    except Exception as e:
        checks['cache'] = {
            'status': 'error',
            'error': str(e)
        }
        # Cache failure is degraded, not unhealthy (app can function without cache)
        if overall_status == "healthy":
            overall_status = "degraded"
        logger.warning(f"Health check - cache error: {e}")

    # Get version from settings or default
    version = getattr(django_settings, 'APP_VERSION', '1.0.0')

    response_data = {
        'status': overall_status,
        'version': version,
        'timestamp': timezone.now().isoformat(),
        'checks': checks
    }

    # Return appropriate HTTP status code
    if overall_status == "unhealthy":
        return Response(response_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    elif overall_status == "degraded":
        return Response(response_data, status=status.HTTP_200_OK)  # Still operational
    else:
        return Response(response_data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def track_usage_view(request):
    """
    Track shortcut usage from the extension.

    POST /api/track-usage/
    Body: { "shortcut_id": 123, "domain": "mail.google.com" (optional) }
    Returns: { "success": true }

    This endpoint:
    1. Increments usage_count on the Shortcut model
    2. Updates last_used_at timestamp
    3. Creates a ShortcutUsageLog entry for detailed analytics
    """
    shortcut_id = request.data.get('shortcut_id')
    domain = request.data.get('domain', '')

    if not shortcut_id:
        return Response(
            {'error': 'shortcut_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        shortcut = Shortcut.objects.get(id=shortcut_id)
    except Shortcut.DoesNotExist:
        return Response(
            {'error': 'Shortcut not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Update shortcut usage stats (atomic operation)
    from django.db.models import F
    Shortcut.objects.filter(id=shortcut_id).update(
        usage_count=F('usage_count') + 1,
        last_used_at=timezone.now()
    )

    # Create detailed usage log
    ShortcutUsageLog.objects.create(
        shortcut=shortcut,
        user=request.user,
        domain=domain[:255] if domain else None  # Truncate to field max length
    )

    logger.info(
        "Shortcut usage tracked",
        shortcut_id=shortcut_id,
        user_id=request.user.id,
        domain=domain
    )

    return Response({'success': True})
