from rest_framework import permissions, viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import authenticate
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import render
from datetime import timedelta

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
        if user.is_superuser:
            # Superusers see all sets
            return ShortcutSet.objects.all().order_by('set_type', 'name')
        # Staff users see: sets they own OR sets shared with them
        return ShortcutSet.objects.filter(
            Q(owner=user) | Q(visible_to=user)
        ).distinct().order_by('set_type', 'name')


class ShortcutViewSet(viewsets.ModelViewSet):
    """
    API endpoint for shortcuts.
    Supports filtering by sets: /api/shortcuts/?sets=birou,cosmin
    """
    serializer_class = ShortcutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Shortcut.objects.all().prefetch_related('sets').order_by("key")

        # Filter by sets if provided in query params
        # Example: /api/shortcuts/?sets=birou,cosmin
        sets_param = self.request.query_params.get('sets', None)
        if sets_param:
            set_names = [s.strip() for s in sets_param.split(',')]

            # Get the ShortcutSet objects to determine their types
            requested_sets = ShortcutSet.objects.filter(name__in=set_names)

            # Separate general and personal sets
            general_sets = requested_sets.filter(set_type='general')
            personal_sets = requested_sets.filter(set_type='personal')

            # Build query combining both types with different ownership rules
            queries = Q()

            # For general sets: get ALL shortcuts in those sets (no ownership filter)
            if general_sets.exists():
                general_set_names = list(general_sets.values_list('name', flat=True))
                queries |= Q(sets__name__in=general_set_names)

            # For personal sets: get ALL shortcuts in those sets
            # Note: The sets themselves are already filtered by ownership/visibility in ShortcutSetViewSet
            # So if user has access to a personal set, they should see all shortcuts in it
            if personal_sets.exists():
                personal_set_names = list(personal_sets.values_list('name', flat=True))
                queries |= Q(sets__name__in=personal_set_names)

            queryset = queryset.filter(queries).distinct()

        # Delta sync: filter by updated_after timestamp
        # Example: /api/shortcuts/?updated_after=2024-10-30T10:00:00Z
        updated_after = self.request.query_params.get('updated_after', None)
        if updated_after:
            queryset = queryset.filter(updated_at__gt=updated_after)

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
