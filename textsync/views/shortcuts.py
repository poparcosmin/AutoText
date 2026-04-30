"""Shortcut and ShortcutSet viewsets — CRUD + list endpoints."""

import structlog

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError, PermissionDenied
from rest_framework.response import Response

from ..models import Shortcut, ShortcutSet
from ..serializers import ShortcutSerializer, ShortcutSetSerializer
from ..cache import get_user_shortcuts_key, get_user_sets_key

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
            timeout = getattr(settings, "CACHE_TIMEOUTS", {}).get("shortcut_sets", 600)
            cache.set(cache_key, response.data, timeout)
            logger.debug(f"Cache set for sets: user={request.user.id}")

        return response

    def get_queryset(self):
        user = self.request.user
        base_qs = ShortcutSet.objects.select_related("owner")
        base_qs = base_qs.prefetch_related("visible_to")
        base_qs = base_qs.annotate(shortcut_count=Count("shortcuts", distinct=True))

        # Business rule (applies to ALL users including superusers):
        # - General sets: visible to everyone
        # - Personal sets: visible ONLY to owner
        # - Shared sets: visible to those in visible_to
        # Note: Superusers can use Django Admin to manage all sets
        return (
            base_qs.filter(
                Q(set_type="general")
                | (Q(set_type="personal") & Q(owner=user))
                | (Q(set_type="shared") & Q(visible_to=user))
            )
            .distinct()
            .order_by("set_type", "name")
        )


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
    Caching: Full list results are cached for 5 minutes. Delta sync skips cache.
    """

    serializer_class = ShortcutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """Override list to add caching (only for full sync, not delta)."""
        updated_after = request.query_params.get("updated_after")
        sets_param = request.query_params.get("sets", "")

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
            timeout = getattr(settings, "CACHE_TIMEOUTS", {}).get("shortcuts", 300)
            cache.set(cache_key, response.data, timeout)
            logger.debug(f"Cache set for shortcuts: user={request.user.id}")

        return response

    def get_queryset(self):
        user = self.request.user
        queryset = Shortcut.objects.select_related("owner", "updated_by")
        queryset = queryset.prefetch_related("sets").order_by("key")

        # Get sets that user has access to (same logic as ShortcutSetViewSet)
        if user.is_superuser:
            accessible_sets = ShortcutSet.objects.all()
        else:
            # User can access:
            # - General sets: visible to everyone
            # - Personal sets: ONLY their own (not via visible_to)
            # - Shared sets: via visible_to
            accessible_sets = ShortcutSet.objects.filter(
                Q(set_type="general")
                | (Q(set_type="personal") & Q(owner=user))
                | (Q(set_type="shared") & Q(visible_to=user))
            ).distinct()

        # Filter by sets parameter (if provided)
        sets_param = self.request.query_params.get("sets", None)

        if sets_param:
            # User specified which sets they want
            requested_set_names = {
                s.strip().lower() for s in sets_param.split(",") if s.strip()
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
                name.lower() for name in requested_sets.values_list("name", flat=True)
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
        updated_after = self.request.query_params.get("updated_after", None)
        if updated_after:
            parsed_updated_after = parse_datetime(updated_after.replace("Z", "+00:00"))
            if not parsed_updated_after:
                raise ParseError("updated_after must be a valid ISO 8601 datetime")

            if timezone.is_naive(parsed_updated_after):
                tz = timezone.get_current_timezone()
                parsed_updated_after = timezone.make_aware(parsed_updated_after, tz)

            queryset = queryset.filter(updated_at__gt=parsed_updated_after)

        # Support search parameter
        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(
                Q(key__icontains=search) | Q(value__icontains=search)
            )

        return queryset

    @action(detail=False, methods=["get"])
    def my(self, request):
        """
        GET /api/shortcuts/my/

        Lists shortcuts the current user can manage:
          - superusers: every shortcut (full edit rights across the team)
          - staff: shortcuts they own + shortcuts in shared sets where
            they're in visible_to (read access shown but edit gated by
            owner check in update/destroy)

        Pre-superuser-fix this returned only owner=user, which left
        non-creator team members with an empty Manage tab even when
        they had legitimate visibility into the shared sets.
        """
        import logging
        from django.db.models import Q

        logger = logging.getLogger(__name__)
        try:
            user = request.user
            if user.is_superuser:
                queryset = Shortcut.objects.all()
            else:
                queryset = Shortcut.objects.filter(
                    Q(owner=user)
                    | Q(sets__visible_to=user)
                    | Q(sets__set_type="general")
                ).distinct()
            queryset = queryset.prefetch_related("sets")
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.exception(f"Error in /shortcuts/my/ for user {request.user}: {e}")
            return Response(
                {"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        """
        POST /api/shortcuts/
        Create a new shortcut owned by the current user.
        Only allows adding to personal sets owned by the user.
        """
        user = request.user
        data = request.data.copy()

        # Validate sets — must be a personal set the user owns OR a general set.
        # Birou (general) is team-shared so anyone can add to it.
        set_ids = data.get("sets", [])
        if set_ids:
            allowed_sets = ShortcutSet.objects.filter(id__in=set_ids).filter(
                Q(set_type="general") | Q(set_type="personal", owner=user)
            )
            if allowed_sets.count() != len(set_ids):
                raise PermissionDenied(
                    "You can only add shortcuts to general sets or your own personal sets."
                )

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=user, updated_by=user)

        # Cache invalidation handled by textsync.signals.post_save on Shortcut
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """
        PUT /api/shortcuts/{id}/

        Edit rules:
          - Owner can always edit their own shortcut.
          - Superuser can edit any shortcut.
          - For shortcuts in `general` sets (Birou): only members of the
            'birou-curators' Django group may edit. Other staff users are
            expected to use Copy-to-Personal and edit their own copy.
          - Personal shortcuts (only in personal sets) stay strict-owner.
        """
        instance = self.get_object()
        user = request.user

        is_owner = instance.owner == user
        is_in_general_set = instance.sets.filter(set_type="general").exists()
        is_birou_curator = (
            is_in_general_set and user.groups.filter(name="birou-curators").exists()
        )
        if not (user.is_superuser or is_owner or is_birou_curator):
            if is_in_general_set:
                raise PermissionDenied(
                    "Only birou-curators or the owner can edit Birou shortcuts. "
                    "Use Copy-to-Personal to make a private edit."
                )
            raise PermissionDenied("Only the owner can edit personal shortcuts.")

        data = request.data.copy()

        # Validate sets — must be a personal set the user owns OR a general set.
        # General sets are shared, so anyone in the team can move shortcuts
        # in/out of them; personal sets stay strict-owner.
        set_ids = data.get("sets", [])
        if set_ids:
            allowed_sets = ShortcutSet.objects.filter(id__in=set_ids).filter(
                Q(set_type="general") | Q(set_type="personal", owner=user)
            )
            if allowed_sets.count() != len(set_ids):
                raise PermissionDenied(
                    "You can only place shortcuts in general sets or your own personal sets."
                )

        serializer = self.get_serializer(instance, data=data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=user)

        # Cache invalidation handled by textsync.signals.post_save on Shortcut
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        DELETE /api/shortcuts/{id}/

        Stricter than update: delete from Birou is allowed ONLY for
        superusers (effectively a Django admin operation). The intent
        is that team-shared shortcuts get curated edits but never
        accidentally vanish — anyone making a mistake can use the admin
        site (which has bulk-undo via history) instead of the API.

          - Owner: can delete their own personal shortcut.
          - Superuser: can delete anything.
          - Anyone else on a Birou shortcut: blocked.
        """
        instance = self.get_object()
        user = request.user

        is_owner = instance.owner == user
        is_in_general_set = instance.sets.filter(set_type="general").exists()
        if not (user.is_superuser or (is_owner and not is_in_general_set)):
            if is_in_general_set:
                raise PermissionDenied(
                    "Birou shortcuts can only be deleted from the Django admin "
                    "(intentionally restricted to prevent accidental team-wide loss)."
                )
            raise PermissionDenied("Only the owner can delete personal shortcuts.")

        instance.delete()
        # Cache invalidation handled by textsync.signals.post_delete on Shortcut
        return Response(status=status.HTTP_204_NO_CONTENT)
