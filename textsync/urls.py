from rest_framework.routers import DefaultRouter

from .views import ShortcutViewSet, ShortcutSetViewSet

router = DefaultRouter()
router.register(r"sets", ShortcutSetViewSet, basename="shortcutset")
router.register(r"shortcuts", ShortcutViewSet, basename="shortcut")

urlpatterns = router.urls
