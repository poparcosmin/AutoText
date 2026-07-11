"""Tests for health_check_view (GET /api/health/)."""

from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

# Use LocMem so the cache check in health_check_view always succeeds (Redis
# may not be available in CI / local test runs).
_LOCMEM_CACHE = {
    "CACHES": {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-health",
        }
    }
}


class HealthCheckTests(APITestCase):
    """Tests for the public health-check endpoint."""

    def setUp(self):
        self.client = APIClient()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    @override_settings(**_LOCMEM_CACHE)
    def test_healthy_returns_200(self):
        """All systems up → 200 with status 'healthy'."""
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "healthy")
        self.assertIn("database", response.data["checks"])
        self.assertIn("cache", response.data["checks"])
        self.assertEqual(response.data["checks"]["database"]["status"], "ok")
        self.assertEqual(response.data["checks"]["cache"]["status"], "ok")

    # ------------------------------------------------------------------
    # Database failure → 503 unhealthy
    # health.py: `with connection.cursor() as cursor: cursor.execute("SELECT 1")`
    # ------------------------------------------------------------------

    def test_db_error_returns_503(self):
        """When the database is unreachable the endpoint returns 503."""
        with patch("textsync.views.health.connection") as mock_conn:
            # Make entering the cursor context manager raise immediately.
            mock_conn.cursor.side_effect = Exception("DB connection refused")

            response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "unhealthy")
        self.assertEqual(response.data["checks"]["database"]["status"], "error")

    # ------------------------------------------------------------------
    # Cache failure → 200 degraded
    # health.py: `cache.set(test_key, "ok", timeout=10)`
    # ------------------------------------------------------------------

    def test_cache_error_returns_200_degraded(self):
        """When the cache is unreachable the endpoint returns 200 with status 'degraded'."""
        with patch("textsync.views.health.cache") as mock_cache:
            mock_cache.set.side_effect = Exception("Cache unavailable")

            response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "degraded")
        self.assertEqual(response.data["checks"]["cache"]["status"], "error")
        # DB should still be ok when only cache fails
        self.assertEqual(response.data["checks"]["database"]["status"], "ok")
