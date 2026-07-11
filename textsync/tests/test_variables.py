"""Tests for UserVariableViewSet (GET/POST/PATCH/DELETE /api/user-variables/)."""

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from ..models import ExpiringToken, UserVariable


class UserVariableTests(APITestCase):
    """CRUD tests for the per-user variables endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.token, plain = ExpiringToken.issue_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {plain}")

        self.var = UserVariable.objects.create(
            user=self.user, name="my_var", value="hello"
        )

    # ------------------------------------------------------------------
    # List scoped to owner
    # ------------------------------------------------------------------

    def test_list_returns_only_own_variables(self):
        """List endpoint returns only the authenticated user's variables."""
        other_user = User.objects.create_user(
            username="otheruser", password="otherpass"
        )
        UserVariable.objects.create(user=other_user, name="other_var", value="other")

        response = self.client.get("/api/user-variables/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [v["name"] for v in response.data]
        self.assertIn("my_var", names)
        self.assertNotIn("other_var", names)
        self.assertEqual(len(names), 1)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def test_create_variable(self):
        """POST creates a variable and returns 201."""
        response = self.client.post(
            "/api/user-variables/",
            {"name": "new_var", "value": "world"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "new_var")
        self.assertTrue(
            UserVariable.objects.filter(user=self.user, name="new_var").exists()
        )

    def test_duplicate_name_returns_400(self):
        """Creating a variable with an already-used name returns 400."""
        response = self.client.post(
            "/api/user-variables/",
            {"name": "my_var", "value": "duplicate"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    # ------------------------------------------------------------------
    # Cross-user access: GET / PATCH / DELETE on another user's variable
    # must return 404 (scope guard in get_queryset)
    # ------------------------------------------------------------------

    def _other_user_var(self):
        """Helper: create another user and their variable; return the variable."""
        other = User.objects.create_user(
            username="otheruser2", password="otherpass2"
        )
        return UserVariable.objects.create(
            user=other, name="other_var", value="other_value"
        )

    def test_cross_user_get_returns_404(self):
        """GET on another user's variable pk returns 404."""
        other_var = self._other_user_var()
        response = self.client.get(f"/api/user-variables/{other_var.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_user_patch_returns_404(self):
        """PATCH on another user's variable pk returns 404."""
        other_var = self._other_user_var()
        response = self.client.patch(
            f"/api/user-variables/{other_var.id}/",
            {"value": "hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # Confirm the value was not changed
        other_var.refresh_from_db()
        self.assertEqual(other_var.value, "other_value")

    def test_cross_user_delete_returns_404(self):
        """DELETE on another user's variable pk returns 404."""
        other_var = self._other_user_var()
        response = self.client.delete(f"/api/user-variables/{other_var.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # Confirm the variable still exists
        self.assertTrue(UserVariable.objects.filter(pk=other_var.id).exists())
