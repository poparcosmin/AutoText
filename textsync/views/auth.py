"""Authentication endpoints — login, logout, verify, refresh."""
import structlog
from datetime import timedelta

from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response

from ..models import ExpiringToken
from ..throttling import LoginRateThrottle, TokenRefreshRateThrottle

logger = structlog.get_logger(__name__)


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
