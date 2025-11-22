from datetime import timedelta

from django.contrib.auth import authenticate
from django.db.models import Q, Count
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ParseError
from rest_framework.response import Response

from .models import Shortcut, ShortcutSet, ExpiringToken
from .serializers import ShortcutSerializer, ShortcutSetSerializer


class ShortcutSetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for listing available shortcut sets.
    Read-only - sets are managed via Django admin.
    Staff users see only their own sets + sets shared with them.
    Superusers see all sets.
    """
    serializer_class = ShortcutSetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        base_qs = ShortcutSet.objects.select_related("owner").prefetch_related("visible_to")
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


class ShortcutViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for shortcuts (READ-ONLY).
    Shortcuts can only be created/edited via Django Admin.
    Supports filtering by sets: /api/shortcuts/?sets=birou,cosmin

    Security: Only returns shortcuts that the authenticated user has access to.
    """
    serializer_class = ShortcutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Shortcut.objects.select_related('owner', 'updated_by').prefetch_related('sets').order_by("key")

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
            requested_set_names = {s.strip().lower() for s in sets_param.split(',') if s.strip()}

            if not requested_set_names:
                return queryset.none()

            # Validate: user can only request sets they have access to (case-insensitive)
            # Build Q filter for case-insensitive matching
            q_filters = Q()
            for name in requested_set_names:
                q_filters |= Q(name__iexact=name)

            requested_sets = accessible_sets.filter(q_filters)

            requested_set_names_found = set(
                name.lower() for name in requested_sets.values_list('name', flat=True)
            )

            # Security check: if user requested sets they don't have access to, return empty
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
                parsed_updated_after = timezone.make_aware(parsed_updated_after, timezone.get_current_timezone())

            queryset = queryset.filter(updated_at__gt=parsed_updated_after)

        return queryset


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    """
    Login endpoint. Returns auth token on success.

    POST /api/auth/login/
    Body: { "username": "user", "password": "pass" }
    Returns: { "token": "abc123...", "expires_at": "2025-04-30T...", "user": {...} }
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
