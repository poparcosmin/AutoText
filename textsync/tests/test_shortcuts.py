"""Tests for Shortcut and ShortcutSet API endpoints."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from ..models import ExpiringToken, Shortcut, ShortcutSet


class ShortcutSetAPITests(APITestCase):
    """Tests for ShortcutSet API endpoints."""

    def setUp(self):
        cache.clear()  # Clear cache to avoid interference from other tests
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.token, plain = ExpiringToken.issue_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {plain}")

        # Create test sets
        self.general_set = ShortcutSet.objects.create(
            name="general-set", set_type="general", owner=self.user
        )
        self.personal_set = ShortcutSet.objects.create(
            name="personal-set", set_type="personal", owner=self.user
        )

    def tearDown(self):
        cache.clear()

    def test_list_sets_authenticated(self):
        """Authenticated user should see their sets."""
        response = self.client.get("/api/sets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_list_sets_unauthenticated(self):
        """Unauthenticated request should fail."""
        self.client.credentials()  # Clear auth

        response = self.client.get("/api/sets/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_sets_includes_shortcut_count(self):
        """Set listing should include shortcut count."""
        # Add a shortcut to the set
        shortcut = Shortcut.objects.create(key="test", value="Test")
        shortcut.sets.add(self.general_set)

        response = self.client.get("/api/sets/")

        general = next(s for s in response.data if s["name"] == "general-set")
        self.assertEqual(general["shortcut_count"], 1)

    def test_user_cannot_see_other_personal_sets(self):
        """User should not see another user's personal sets."""
        other_user = User.objects.create_user(username="other", password="pass")
        ShortcutSet.objects.create(
            name="other-personal", set_type="personal", owner=other_user
        )

        response = self.client.get("/api/sets/")

        set_names = [s["name"] for s in response.data]
        self.assertNotIn("other-personal", set_names)


class ShortcutAPITests(APITestCase):
    """Tests for Shortcut API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.token, plain = ExpiringToken.issue_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {plain}")

        # Create test data
        self.shortcut_set = ShortcutSet.objects.create(
            name="test-set", set_type="general", owner=self.user
        )
        self.shortcut = Shortcut.objects.create(
            key="hello", value="Hello, World!", owner=self.user
        )
        self.shortcut.sets.add(self.shortcut_set)

    def test_list_shortcuts_authenticated(self):
        """Authenticated user should see shortcuts."""
        response = self.client.get("/api/shortcuts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["key"], "hello")

    def test_list_shortcuts_filter_by_set(self):
        """Can filter shortcuts by set name."""
        response = self.client.get("/api/shortcuts/", {"sets": "test-set"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_shortcuts_filter_by_nonexistent_set(self):
        """Filtering by non-existent set returns empty."""
        response = self.client.get("/api/shortcuts/", {"sets": "nonexistent"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_list_shortcuts_delta_sync(self):
        """Delta sync with updated_after works."""
        # Get current time
        now = timezone.now()

        # Create a newer shortcut
        new_shortcut = Shortcut.objects.create(
            key="new", value="New shortcut", owner=self.user
        )
        new_shortcut.sets.add(self.shortcut_set)

        # Request shortcuts updated after 'now'
        response = self.client.get(
            "/api/shortcuts/",
            {"updated_after": (now - timedelta(seconds=1)).isoformat()},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_shortcuts_include_set_info(self):
        """Shortcuts should include set names and types."""
        response = self.client.get("/api/shortcuts/")

        shortcut_data = response.data[0]
        self.assertIn("set_names", shortcut_data)
        self.assertIn("set_types", shortcut_data)
        self.assertIn("test-set", shortcut_data["set_names"])

    def test_create_shortcut_with_sets(self):
        """Creating a shortcut should correctly save the sets relationship."""
        # Create a personal set for the user
        personal_set = ShortcutSet.objects.create(
            name="my-personal-set", set_type="personal", owner=self.user
        )

        response = self.client.post(
            "/api/shortcuts/",
            {
                "key": "new_shortcut",
                "content_type": "text",
                "value": "New value",
                "sets": [personal_set.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("set_names", response.data)
        self.assertIn("my-personal-set", response.data["set_names"])

        # Verify in database
        shortcut = Shortcut.objects.get(key="new_shortcut")
        self.assertEqual(shortcut.sets.count(), 1)
        self.assertEqual(shortcut.sets.first().name, "my-personal-set")

    def test_copy_birou_to_personal_creates_independent_shortcut(self):
        """Copying a Birou shortcut to Personal should create an independent shortcut."""
        # Create Birou set (general type)
        birou_set = ShortcutSet.objects.create(
            name="Birou", set_type="general", owner=None
        )

        # Create personal set
        personal_set = ShortcutSet.objects.create(
            name="Personal", set_type="personal", owner=self.user
        )

        # Create a Birou shortcut (owned by None or staff)
        birou_shortcut = Shortcut.objects.create(
            key="shared_key",
            value="Original Birou value",
            owner=None,  # Birou shortcuts typically have no owner
        )
        birou_shortcut.sets.add(birou_set)

        # Simulate "copy to personal" by creating a new shortcut with same key
        response = self.client.post(
            "/api/shortcuts/",
            {
                "key": "shared_key",  # Same key as Birou
                "content_type": "text",
                "value": "My personal version",
                "sets": [personal_set.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify we now have two shortcuts with the same key
        shortcuts = Shortcut.objects.filter(key="shared_key")
        self.assertEqual(shortcuts.count(), 2)

        # Delete the personal shortcut
        personal_shortcut = Shortcut.objects.get(key="shared_key", owner=self.user)
        personal_shortcut_id = personal_shortcut.id

        delete_response = self.client.delete(f"/api/shortcuts/{personal_shortcut_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify Birou shortcut still exists
        birou_shortcut.refresh_from_db()
        self.assertEqual(birou_shortcut.key, "shared_key")
        self.assertEqual(birou_shortcut.value, "Original Birou value")

        # Only Birou shortcut should remain
        shortcuts = Shortcut.objects.filter(key="shared_key")
        self.assertEqual(shortcuts.count(), 1)
