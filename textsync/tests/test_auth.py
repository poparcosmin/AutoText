"""Tests for authentication endpoints: login, logout, verify, refresh."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from ..models import ExpiringToken


class AuthenticationAPITests(APITestCase):
    """Tests for authentication endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_login_success(self):
        """Valid credentials should return token."""
        response = self.client.post(
            "/api/auth/login/", {"username": "testuser", "password": "testpass123"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertIn("expires_at", response.data)
        self.assertIn("user", response.data)

    def test_login_invalid_credentials(self):
        """Invalid credentials should return 401."""
        response = self.client.post(
            "/api/auth/login/", {"username": "testuser", "password": "wrongpass"}
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_missing_fields(self):
        """Missing fields should return 400."""
        response = self.client.post("/api/auth/login/", {"username": "testuser"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_inactive_user(self):
        """Inactive user returns 401 (same as invalid creds for security)."""
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            "/api/auth/login/", {"username": "testuser", "password": "testpass123"}
        )

        # Django's authenticate() returns None for inactive users, which is more secure
        # (doesn't reveal that the account exists but is disabled)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_success(self):
        """Logout should delete token."""
        # First login
        token = ExpiringToken.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post("/api/auth/logout/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(ExpiringToken.objects.filter(user=self.user).exists())

    def test_verify_token_valid(self):
        """Valid token should return user info."""
        token = ExpiringToken.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get("/api/auth/verify/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])

    def test_verify_token_expired(self):
        """Expired token should fail authentication."""
        token = ExpiringToken.objects.create(user=self.user)
        token.expires_at = timezone.now() - timedelta(days=1)
        token.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get("/api/auth/verify/")

        # Should fail auth before reaching view
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_within_window(self):
        """Token refresh should work within 30-day window."""
        token = ExpiringToken.objects.create(user=self.user)
        # Set expiration to 20 days from now (within 30-day refresh window)
        token.expires_at = timezone.now() + timedelta(days=20)
        token.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post("/api/auth/refresh/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        # New token should be different
        self.assertNotEqual(response.data["token"], token.key)

    def test_refresh_token_too_early(self):
        """Token refresh should be rejected if too early."""
        token = ExpiringToken.objects.create(user=self.user)
        # Default is 180 days, so 150 days left is outside 30-day window

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post("/api/auth/refresh/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("refresh not needed", response.data.get("message", ""))
