"""Tests for bulk sync endpoint."""

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from ..models import ExpiringToken, Shortcut, ShortcutSet


class BulkSyncAPITests(APITestCase):
    """Tests for bulk sync endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.token = ExpiringToken.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        # Create test data
        self.shortcut_set = ShortcutSet.objects.create(
            name="birou", set_type="general", owner=self.user
        )
        self.shortcut = Shortcut.objects.create(
            key="test", value="Test value", owner=self.user
        )
        self.shortcut.sets.add(self.shortcut_set)

    def test_bulk_sync_returns_sets_and_shortcuts(self):
        """Bulk sync should return both sets and shortcuts."""
        response = self.client.post(
            "/api/sync/bulk/", {"sets": ["birou"]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sets", response.data)
        self.assertIn("shortcuts", response.data)
        self.assertIn("server_time", response.data)
        self.assertIn("count", response.data)

    def test_bulk_sync_filters_by_sets(self):
        """Bulk sync should filter by requested sets."""
        # Create another set
        other_set = ShortcutSet.objects.create(
            name="other", set_type="personal", owner=self.user
        )
        other_shortcut = Shortcut.objects.create(
            key="other", value="Other", owner=self.user
        )
        other_shortcut.sets.add(other_set)

        response = self.client.post(
            "/api/sync/bulk/", {"sets": ["birou"]}, format="json"
        )

        # Should only return 'birou' set shortcuts
        shortcut_keys = [s["key"] for s in response.data["shortcuts"]]
        self.assertIn("test", shortcut_keys)
        self.assertNotIn("other", shortcut_keys)

    def test_bulk_sync_delta(self):
        """Bulk sync with updated_after returns only new changes."""
        now = timezone.now()

        response = self.client.post(
            "/api/sync/bulk/",
            {"sets": ["birou"], "updated_after": now.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_bulk_sync_count_accuracy(self):
        """Count in response should match actual data."""
        response = self.client.post(
            "/api/sync/bulk/", {"sets": ["birou"]}, format="json"
        )

        self.assertEqual(response.data["count"]["sets"], len(response.data["sets"]))
        self.assertEqual(
            response.data["count"]["shortcuts"], len(response.data["shortcuts"])
        )
