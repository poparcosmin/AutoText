from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ShortcutViewSet,
    ShortcutSetViewSet,
    login_view,
    logout_view,
    verify_token_view,
    refresh_token_view,
    bulk_sync_view,
    health_check_view,
    track_usage_view,
)

router = DefaultRouter()
router.register(r"sets", ShortcutSetViewSet, basename="shortcutset")
router.register(r"shortcuts", ShortcutViewSet, basename="shortcut")

urlpatterns = [
    # Health check (for monitoring/load balancers)
    path('health/', health_check_view, name='health_check'),

    # Auth endpoints
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/verify/', verify_token_view, name='verify_token'),
    path('auth/refresh/', refresh_token_view, name='refresh_token'),

    # Bulk operations
    path('sync/bulk/', bulk_sync_view, name='bulk_sync'),

    # Analytics
    path('track-usage/', track_usage_view, name='track_usage'),
] + router.urls
