"""Tests for cache utilities.

Uses LocMemCache to stay independent of whether Redis runs on the dev machine.
Production uses django-redis (see settings.CACHES).
"""
from django.core.cache import cache
from django.test import TestCase, override_settings

from ..cache import (
    get_cache_key,
    get_user_shortcuts_key,
    get_user_sets_key,
    invalidate_user_cache,
)


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'test-cache',
        }
    }
)
class CacheTests(TestCase):
    """Tests for cache utilities."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_get_cache_key_format(self):
        """Cache keys should be formatted correctly."""
        key = get_cache_key('prefix', 'arg1', 'arg2')
        self.assertEqual(key, 'prefix:arg1:arg2')

    def test_get_cache_key_skips_none(self):
        """None values should be skipped in cache key."""
        key = get_cache_key('prefix', 'arg1', None, 'arg2')
        self.assertEqual(key, 'prefix:arg1:arg2')

    def test_get_user_shortcuts_key(self):
        """User shortcuts key should include user ID."""
        key = get_user_shortcuts_key(123)
        self.assertIn('123', key)
        self.assertIn('shortcuts', key)

    def test_get_user_sets_key(self):
        """User sets key should include user ID."""
        key = get_user_sets_key(456)
        self.assertIn('456', key)
        self.assertIn('sets', key)

    def test_invalidate_user_cache(self):
        """Invalidate should clear user's cache entries."""
        user_id = 789

        # Set some cache entries
        cache.set(get_user_shortcuts_key(user_id), 'data1')
        cache.set(get_user_sets_key(user_id), 'data2')

        # Verify they exist
        self.assertIsNotNone(cache.get(get_user_shortcuts_key(user_id)))

        # Invalidate
        invalidate_user_cache(user_id)

        # Verify they're gone
        self.assertIsNone(cache.get(get_user_shortcuts_key(user_id)))
        self.assertIsNone(cache.get(get_user_sets_key(user_id)))
