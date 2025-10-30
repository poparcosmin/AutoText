from rest_framework import permissions, viewsets

from .models import Shortcut, ShortcutSet
from .serializers import ShortcutSerializer, ShortcutSetSerializer


class ShortcutSetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for listing available shortcut sets.
    Read-only - sets are managed via Django admin.
    """
    queryset = ShortcutSet.objects.all().order_by('set_type', 'name')
    serializer_class = ShortcutSetSerializer
    permission_classes = [permissions.IsAuthenticated]


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
            queryset = queryset.filter(sets__name__in=set_names).distinct()

        return queryset
