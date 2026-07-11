"""Tests for track_usage_view (POST /api/track-usage/)."""

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from ..models import ExpiringToken, Shortcut, ShortcutSet


class TrackUsageTests(APITestCase):
    """Tests for the usage-tracking endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.token, plain = ExpiringToken.issue_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {plain}")

        # A general set is visible to all authenticated users.
        self.general_set = ShortcutSet.objects.create(
            name="general-set", set_type="general", owner=self.user
        )
        self.shortcut = Shortcut.objects.create(
            key="hello", value="Hello, World!", owner=self.user, usage_count=0
        )
        self.shortcut.sets.add(self.general_set)

    # ------------------------------------------------------------------
    # Validation: missing shortcut_id → 400
    # ------------------------------------------------------------------

    def test_missing_shortcut_id_returns_400(self):
        """POST without shortcut_id should return 400."""
        response = self.client.post("/api/track-usage/", {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("shortcut_id", response.data.get("error", ""))

    # ------------------------------------------------------------------
    # Non-existent shortcut → 404
    # ------------------------------------------------------------------

    def test_nonexistent_shortcut_returns_404(self):
        """POST with a shortcut_id that doesn't exist should return 404."""
        response = self.client.post("/api/track-usage/", {"shortcut_id": 99999})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------------------------
    # Happy path: accessible shortcut, usage_count incremented
    # ------------------------------------------------------------------

    def test_tracking_increments_usage_count(self):
        """Tracking a reachable shortcut increments its usage_count."""
        response = self.client.post(
            "/api/track-usage/", {"shortcut_id": self.shortcut.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get("success"))

        self.shortcut.refresh_from_db()
        self.assertEqual(self.shortcut.usage_count, 1)

    def test_tracking_twice_increments_twice(self):
        """Each successful track call increments usage_count by 1."""
        self.client.post("/api/track-usage/", {"shortcut_id": self.shortcut.id})
        self.client.post("/api/track-usage/", {"shortcut_id": self.shortcut.id})

        self.shortcut.refresh_from_db()
        self.assertEqual(self.shortcut.usage_count, 2)

    # ------------------------------------------------------------------
    # IDOR / access-control regression: shortcut in another user's
    # personal set must be invisible → 404 (not 403, to avoid oracle)
    # ------------------------------------------------------------------

    def test_idor_other_users_personal_shortcut_returns_404(self):
        """Tracking a shortcut in another user's personal set returns 404."""
        other_user = User.objects.create_user(
            username="otheruser", password="otherpass123"
        )
        other_personal_set = ShortcutSet.objects.create(
            name="other-personal", set_type="personal", owner=other_user
        )
        other_shortcut = Shortcut.objects.create(
            key="secret", value="Secret expansion", owner=other_user
        )
        other_shortcut.sets.add(other_personal_set)

        response = self.client.post(
            "/api/track-usage/", {"shortcut_id": other_shortcut.id}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Confirm usage_count was NOT touched
        other_shortcut.refresh_from_db()
        self.assertEqual(other_shortcut.usage_count, 0)
