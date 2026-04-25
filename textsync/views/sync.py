"""Bulk sync endpoint — delegates to sync_service.

Caching and cache invalidation live in textsync.services.sync_service and
textsync.cache.invalidate_user_cache (driven by signals). This view is a
thin HTTP adapter on top of that service.
"""
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response

from ..services.sync_service import build_bulk_sync_response
from ..throttling import BulkSyncRateThrottle


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
    data = build_bulk_sync_response(
        user=request.user,
        requested_sets=request.data.get('sets', []),
        updated_after=request.data.get('updated_after'),
    )
    return Response(data)
