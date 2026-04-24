"""Shortcut usage tracking endpoint."""
import structlog

from django.db.models import F
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..models import Shortcut, ShortcutUsageLog

logger = structlog.get_logger(__name__)


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
