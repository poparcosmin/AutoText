"""Bulk sync business logic.

Extracts the complex algorithm from bulk_sync_view so the viewset becomes a thin
delegator. Hides: cache key scheme, accessible-sets resolution, name filtering,
serialization, delta-sync filtering, and response construction.

Note on accessible_sets: this module preserves the existing bulk-sync rule
(more permissive than ShortcutViewSet — see audit notes). Do not reconcile
without an explicit behavior-change ticket.
"""
from typing import Any

import structlog
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, Count, QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ..models import Shortcut, ShortcutSet
from ..serializers import ShortcutSerializer, ShortcutSetSerializer

logger = structlog.get_logger(__name__)


def _build_cache_key(user_id: int, requested_sets: list[str]) -> str:
    sets_key = ",".join(sorted(requested_sets)) if requested_sets else "all"
    return f"bulk_sync:{user_id}:{sets_key}"


def _get_accessible_sets(user: Any, requested_sets: list[str]) -> QuerySet[ShortcutSet]:
    """Resolve the queryset of sets this user can bulk-sync.

    NOTE: Rule differs from ShortcutViewSet — bulk sync treats any owned set or
    any set where user is in visible_to as accessible, regardless of set_type.
    Preserved verbatim from the pre-split behavior.
    """
    if user.is_superuser:
        accessible_sets = ShortcutSet.objects.all()
    else:
        accessible_sets = ShortcutSet.objects.filter(
            Q(set_type='general') | Q(owner=user) | Q(visible_to=user)
        ).distinct()

    if requested_sets:
        q_filters = Q()
        for name in requested_sets:
            q_filters |= Q(name__iexact=name.strip())
        accessible_sets = accessible_sets.filter(q_filters)

    return accessible_sets


def _serialize_sets(accessible_sets: QuerySet[ShortcutSet]) -> list[dict[str, Any]]:
    sets_qs = accessible_sets.select_related("owner").prefetch_related("visible_to")
    sets_qs = sets_qs.annotate(shortcut_count=Count("shortcuts", distinct=True))
    return ShortcutSetSerializer(sets_qs, many=True).data


def _serialize_shortcuts(
    accessible_sets: QuerySet[ShortcutSet], updated_after: str | None
) -> list[dict[str, Any]]:
    shortcuts_qs = Shortcut.objects.filter(sets__in=accessible_sets).distinct()
    shortcuts_qs = shortcuts_qs.select_related('owner', 'updated_by')
    shortcuts_qs = shortcuts_qs.prefetch_related('sets', 'aliases')
    shortcuts_qs = shortcuts_qs.order_by("key")

    if updated_after:
        parsed_updated_after = parse_datetime(updated_after.replace('Z', '+00:00'))
        if parsed_updated_after:
            if timezone.is_naive(parsed_updated_after):
                tz = timezone.get_current_timezone()
                parsed_updated_after = timezone.make_aware(parsed_updated_after, tz)
            shortcuts_qs = shortcuts_qs.filter(updated_at__gt=parsed_updated_after)

    return ShortcutSerializer(shortcuts_qs, many=True).data


def build_bulk_sync_response(
    user: Any, requested_sets: list[str], updated_after: str | None
) -> dict[str, Any]:
    """Return a dict with sets + shortcuts + metadata. Caller wraps in Response().

    Caches full-sync results only. Delta syncs (updated_after set) skip cache.
    """
    cache_key = _build_cache_key(user.id, requested_sets)

    if not updated_after:
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            logger.debug(f"Cache hit for bulk sync: user={user.id}")
            return cached_response

    accessible_sets = _get_accessible_sets(user, requested_sets)
    sets_data = _serialize_sets(accessible_sets)
    shortcuts_data = _serialize_shortcuts(accessible_sets, updated_after)

    response_data = {
        'sets': sets_data,
        'shortcuts': shortcuts_data,
        'server_time': timezone.now().isoformat(),
        'count': {
            'sets': len(sets_data),
            'shortcuts': len(shortcuts_data),
        },
    }

    if not updated_after:
        timeout = getattr(settings, 'CACHE_TIMEOUTS', {}).get('shortcuts', 300)
        cache.set(cache_key, response_data, timeout)
        logger.debug(f"Cache set for bulk sync: user={user.id}")

    logger.info(
        f"Bulk sync: user={user.id}, sets={len(sets_data)}, "
        f"shortcuts={len(shortcuts_data)}"
    )

    return response_data
