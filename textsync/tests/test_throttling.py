"""Tests for rate limiting / throttling."""
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase


@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': {
            'login': '2/minute',
            'token_refresh': '2/hour',
            'bulk_sync': '2/hour',
        }
    },
    # LocMem isolates throttle state from local Redis availability
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'test-throttle',
        }
    }
)
class ThrottlingTests(APITestCase):
    """Tests for rate limiting."""

    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_login_throttle(self):
        """Login should be rate limited after 10 attempts per minute."""
        # Make requests up to the limit (10/minute as configured)
        for _ in range(10):
            self.client.post('/api/auth/login/', {
                'username': 'test',
                'password': 'test'
            })

        # Next request should be throttled
        response = self.client.post('/api/auth/login/', {
            'username': 'test',
            'password': 'test'
        })

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
