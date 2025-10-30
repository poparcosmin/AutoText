from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ShortcutViewSet, ShortcutSetViewSet, login_view, logout_view, verify_token_view

router = DefaultRouter()
router.register(r"sets", ShortcutSetViewSet, basename="shortcutset")
router.register(r"shortcuts", ShortcutViewSet, basename="shortcut")

urlpatterns = [
    # Auth endpoints
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/verify/', verify_token_view, name='verify_token'),
] + router.urls
