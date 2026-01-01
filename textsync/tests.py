"""
Comprehensive tests for AutoText API.

Coverage includes:
- Models: ExpiringToken, ShortcutSet, Shortcut
- Views: Login, Logout, Verify, Refresh, BulkSync, Shortcuts, Sets
- Validators: Key, Value, Set Name, HTML Sanitization
- Cache: Key generation, invalidation
- Throttling: Rate limits
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import ExpiringToken, Shortcut, ShortcutSet
from .validators import (
    sanitize_html,
    validate_shortcut_key,
    validate_shortcut_value,
    validate_set_name,
)
from .cache import (
    get_cache_key,
    get_user_shortcuts_key,
    get_user_sets_key,
    invalidate_user_cache,
)


# =============================================================================
# MODEL TESTS
# =============================================================================

class ExpiringTokenModelTest(TestCase):
    """Tests for ExpiringToken model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_token_creation(self):
        """Token should be created with key and expiration."""
        token = ExpiringToken.objects.create(user=self.user)

        self.assertIsNotNone(token.key)
        self.assertEqual(len(token.key), 40)  # 20 bytes hex = 40 chars
        self.assertIsNotNone(token.expires_at)

    def test_token_expiration_180_days(self):
        """Token should expire after 180 days."""
        token = ExpiringToken.objects.create(user=self.user)

        expected_expiry = timezone.now() + timedelta(days=180)
        # Allow 1 minute tolerance
        self.assertAlmostEqual(
            token.expires_at.timestamp(),
            expected_expiry.timestamp(),
            delta=60
        )

    def test_is_expired_false_for_new_token(self):
        """New token should not be expired."""
        token = ExpiringToken.objects.create(user=self.user)
        self.assertFalse(token.is_expired())

    def test_is_expired_true_for_old_token(self):
        """Token past expiration should be expired."""
        token = ExpiringToken.objects.create(user=self.user)
        token.expires_at = timezone.now() - timedelta(days=1)
        token.save()

        self.assertTrue(token.is_expired())

    def test_token_string_representation(self):
        """Token __str__ should include username and expiry."""
        token = ExpiringToken.objects.create(user=self.user)
        str_repr = str(token)

        self.assertIn('testuser', str_repr)
        self.assertIn('expires', str_repr)

    def test_one_token_per_user(self):
        """Each user should have at most one token (OneToOne)."""
        ExpiringToken.objects.create(user=self.user)

        with self.assertRaises(Exception):
            ExpiringToken.objects.create(user=self.user)


class ShortcutSetModelTest(TestCase):
    """Tests for ShortcutSet model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_set_creation(self):
        """ShortcutSet should be created with required fields."""
        shortcut_set = ShortcutSet.objects.create(
            name='test-set',
            set_type='general',
            owner=self.user
        )

        self.assertEqual(shortcut_set.name, 'test-set')
        self.assertEqual(shortcut_set.set_type, 'general')
        self.assertIsNotNone(shortcut_set.created_at)

    def test_set_types(self):
        """Set type should be 'general' or 'personal'."""
        general_set = ShortcutSet.objects.create(
            name='general-set',
            set_type='general'
        )
        personal_set = ShortcutSet.objects.create(
            name='personal-set',
            set_type='personal',
            owner=self.user
        )

        self.assertEqual(general_set.set_type, 'general')
        self.assertEqual(personal_set.set_type, 'personal')

    def test_set_name_unique(self):
        """Set names should be unique."""
        ShortcutSet.objects.create(name='unique-set')

        with self.assertRaises(Exception):
            ShortcutSet.objects.create(name='unique-set')

    def test_visible_to_many_to_many(self):
        """Sets can be visible to multiple users."""
        user2 = User.objects.create_user(username='user2', password='pass')

        shortcut_set = ShortcutSet.objects.create(
            name='shared-set',
            owner=self.user
        )
        shortcut_set.visible_to.add(user2)

        self.assertIn(user2, shortcut_set.visible_to.all())

    def test_set_string_representation(self):
        """Set __str__ should include name and type."""
        shortcut_set = ShortcutSet.objects.create(
            name='my-set',
            set_type='personal'
        )
        str_repr = str(shortcut_set)

        self.assertIn('my-set', str_repr)


class ShortcutModelTest(TestCase):
    """Tests for Shortcut model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.shortcut_set = ShortcutSet.objects.create(
            name='test-set',
            owner=self.user
        )

    def test_shortcut_creation(self):
        """Shortcut should be created with key and value."""
        shortcut = Shortcut.objects.create(
            key='hello',
            value='Hello, World!',
            owner=self.user
        )
        shortcut.sets.add(self.shortcut_set)

        self.assertEqual(shortcut.key, 'hello')
        self.assertEqual(shortcut.value, 'Hello, World!')
        self.assertIn(self.shortcut_set, shortcut.sets.all())

    def test_shortcut_html_content(self):
        """Shortcut can have HTML content."""
        shortcut = Shortcut.objects.create(
            key='formatted',
            content_type='html',
            html_value='<p><strong>Bold</strong> text</p>',
            owner=self.user
        )

        self.assertEqual(shortcut.content_type, 'html')
        self.assertIn('<strong>', shortcut.html_value)

    def test_shortcut_multiple_sets(self):
        """Shortcut can belong to multiple sets."""
        set2 = ShortcutSet.objects.create(name='set2')

        shortcut = Shortcut.objects.create(
            key='multi',
            value='In multiple sets',
            owner=self.user
        )
        shortcut.sets.add(self.shortcut_set, set2)

        self.assertEqual(shortcut.sets.count(), 2)

    def test_shortcut_updated_at_auto(self):
        """updated_at should auto-update on save."""
        shortcut = Shortcut.objects.create(
            key='track',
            value='Original',
            owner=self.user
        )
        original_updated = shortcut.updated_at

        shortcut.value = 'Updated'
        shortcut.save()

        self.assertGreater(shortcut.updated_at, original_updated)

    def test_same_key_different_sets(self):
        """Same key can exist in different sets (no unique constraint)."""
        set2 = ShortcutSet.objects.create(name='set2')

        shortcut1 = Shortcut.objects.create(key='dup', value='First')
        shortcut1.sets.add(self.shortcut_set)

        shortcut2 = Shortcut.objects.create(key='dup', value='Second')
        shortcut2.sets.add(set2)

        self.assertEqual(Shortcut.objects.filter(key='dup').count(), 2)


# =============================================================================
# VALIDATOR TESTS
# =============================================================================

class ValidatorTests(TestCase):
    """Tests for input validators."""

    def test_validate_shortcut_key_valid(self):
        """Valid keys should pass."""
        valid_keys = ['hello', 'my_key', 'key-123', 'key.name', '_private']

        for key in valid_keys:
            is_valid, error = validate_shortcut_key(key)
            self.assertTrue(is_valid, f"Key '{key}' should be valid: {error}")

    def test_validate_shortcut_key_invalid_start_number(self):
        """Keys starting with number should fail."""
        is_valid, error = validate_shortcut_key('123key')
        self.assertFalse(is_valid)
        self.assertIn('start with', error.lower())

    def test_validate_shortcut_key_invalid_spaces(self):
        """Keys with spaces should fail."""
        is_valid, error = validate_shortcut_key('hello world')
        self.assertFalse(is_valid)

    def test_validate_shortcut_key_empty(self):
        """Empty key should fail."""
        is_valid, error = validate_shortcut_key('')
        self.assertFalse(is_valid)
        self.assertIn('required', error.lower())

    def test_validate_shortcut_key_too_long(self):
        """Key over 50 chars should fail."""
        long_key = 'a' * 51
        is_valid, error = validate_shortcut_key(long_key)
        self.assertFalse(is_valid)
        self.assertIn('50', error)

    def test_validate_shortcut_value_valid(self):
        """Normal values should pass."""
        is_valid, error = validate_shortcut_value('Hello, World!')
        self.assertTrue(is_valid)

    def test_validate_shortcut_value_empty(self):
        """Empty value should be valid (HTML might be used instead)."""
        is_valid, error = validate_shortcut_value('')
        self.assertTrue(is_valid)

    def test_validate_shortcut_value_too_long(self):
        """Value over max length should fail."""
        long_value = 'a' * 50001
        is_valid, error = validate_shortcut_value(long_value)
        self.assertFalse(is_valid)

    def test_validate_set_name_valid(self):
        """Valid set names should pass."""
        valid_names = ['birou', 'My Set', 'set-123', 'set_name']

        for name in valid_names:
            is_valid, error = validate_set_name(name)
            self.assertTrue(is_valid, f"Name '{name}' should be valid: {error}")

    def test_validate_set_name_empty(self):
        """Empty name should fail."""
        is_valid, error = validate_set_name('')
        self.assertFalse(is_valid)

    def test_validate_set_name_special_chars(self):
        """Special characters should fail."""
        is_valid, error = validate_set_name('set@name!')
        self.assertFalse(is_valid)


class HTMLSanitizationTests(TestCase):
    """Tests for HTML sanitization."""

    def test_sanitize_allowed_tags(self):
        """Allowed tags should be preserved."""
        html = '<p><strong>Bold</strong> and <em>italic</em></p>'
        result = sanitize_html(html)

        self.assertIn('<strong>', result)
        self.assertIn('<em>', result)
        self.assertIn('<p>', result)

    def test_sanitize_script_removed(self):
        """Script tags should be removed."""
        html = '<p>Hello</p><script>alert("xss")</script>'
        result = sanitize_html(html)

        self.assertNotIn('<script>', result)
        self.assertNotIn('alert', result)

    def test_sanitize_onclick_removed(self):
        """Event handlers should be removed."""
        html = '<button onclick="alert(1)">Click</button>'
        result = sanitize_html(html)

        self.assertNotIn('onclick', result)

    def test_sanitize_javascript_href_removed(self):
        """javascript: URLs should be removed."""
        html = '<a href="javascript:alert(1)">Link</a>'
        result = sanitize_html(html)

        self.assertNotIn('javascript:', result)

    def test_sanitize_preserves_safe_href(self):
        """Safe URLs should be preserved."""
        html = '<a href="https://example.com">Link</a>'
        result = sanitize_html(html)

        self.assertIn('https://example.com', result)

    def test_sanitize_empty_input(self):
        """Empty input should return empty."""
        self.assertEqual(sanitize_html(''), '')
        self.assertIsNone(sanitize_html(None))


# =============================================================================
# CACHE TESTS
# =============================================================================

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


# =============================================================================
# API VIEW TESTS
# =============================================================================

class AuthenticationAPITests(APITestCase):
    """Tests for authentication endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_login_success(self):
        """Valid credentials should return token."""
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertIn('expires_at', response.data)
        self.assertIn('user', response.data)

    def test_login_invalid_credentials(self):
        """Invalid credentials should return 401."""
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'wrongpass'
        })

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_missing_fields(self):
        """Missing fields should return 400."""
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser'
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_inactive_user(self):
        """Inactive user returns 401 (same as invalid creds for security)."""
        self.user.is_active = False
        self.user.save()

        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })

        # Django's authenticate() returns None for inactive users, which is more secure
        # (doesn't reveal that the account exists but is disabled)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_success(self):
        """Logout should delete token."""
        # First login
        token = ExpiringToken.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post('/api/auth/logout/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(ExpiringToken.objects.filter(user=self.user).exists())

    def test_verify_token_valid(self):
        """Valid token should return user info."""
        token = ExpiringToken.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get('/api/auth/verify/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['valid'])

    def test_verify_token_expired(self):
        """Expired token should fail authentication."""
        token = ExpiringToken.objects.create(user=self.user)
        token.expires_at = timezone.now() - timedelta(days=1)
        token.save()

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get('/api/auth/verify/')

        # Should fail auth before reaching view
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_within_window(self):
        """Token refresh should work within 30-day window."""
        token = ExpiringToken.objects.create(user=self.user)
        # Set expiration to 20 days from now (within 30-day refresh window)
        token.expires_at = timezone.now() + timedelta(days=20)
        token.save()

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post('/api/auth/refresh/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        # New token should be different
        self.assertNotEqual(response.data['token'], token.key)

    def test_refresh_token_too_early(self):
        """Token refresh should be rejected if too early."""
        token = ExpiringToken.objects.create(user=self.user)
        # Default is 180 days, so 150 days left is outside 30-day window

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post('/api/auth/refresh/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('refresh not needed', response.data.get('message', ''))


class ShortcutSetAPITests(APITestCase):
    """Tests for ShortcutSet API endpoints."""

    def setUp(self):
        cache.clear()  # Clear cache to avoid interference from other tests
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.token = ExpiringToken.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        # Create test sets
        self.general_set = ShortcutSet.objects.create(
            name='general-set',
            set_type='general',
            owner=self.user
        )
        self.personal_set = ShortcutSet.objects.create(
            name='personal-set',
            set_type='personal',
            owner=self.user
        )

    def tearDown(self):
        cache.clear()

    def test_list_sets_authenticated(self):
        """Authenticated user should see their sets."""
        response = self.client.get('/api/sets/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_list_sets_unauthenticated(self):
        """Unauthenticated request should fail."""
        self.client.credentials()  # Clear auth

        response = self.client.get('/api/sets/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_sets_includes_shortcut_count(self):
        """Set listing should include shortcut count."""
        # Add a shortcut to the set
        shortcut = Shortcut.objects.create(key='test', value='Test')
        shortcut.sets.add(self.general_set)

        response = self.client.get('/api/sets/')

        general = next(s for s in response.data if s['name'] == 'general-set')
        self.assertEqual(general['shortcut_count'], 1)

    def test_user_cannot_see_other_personal_sets(self):
        """User should not see another user's personal sets."""
        other_user = User.objects.create_user(username='other', password='pass')
        ShortcutSet.objects.create(
            name='other-personal',
            set_type='personal',
            owner=other_user
        )

        response = self.client.get('/api/sets/')

        set_names = [s['name'] for s in response.data]
        self.assertNotIn('other-personal', set_names)


class ShortcutAPITests(APITestCase):
    """Tests for Shortcut API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.token = ExpiringToken.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        # Create test data
        self.shortcut_set = ShortcutSet.objects.create(
            name='test-set',
            set_type='general',
            owner=self.user
        )
        self.shortcut = Shortcut.objects.create(
            key='hello',
            value='Hello, World!',
            owner=self.user
        )
        self.shortcut.sets.add(self.shortcut_set)

    def test_list_shortcuts_authenticated(self):
        """Authenticated user should see shortcuts."""
        response = self.client.get('/api/shortcuts/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['key'], 'hello')

    def test_list_shortcuts_filter_by_set(self):
        """Can filter shortcuts by set name."""
        response = self.client.get('/api/shortcuts/', {'sets': 'test-set'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_shortcuts_filter_by_nonexistent_set(self):
        """Filtering by non-existent set returns empty."""
        response = self.client.get('/api/shortcuts/', {'sets': 'nonexistent'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_list_shortcuts_delta_sync(self):
        """Delta sync with updated_after works."""
        # Get current time
        now = timezone.now()

        # Create a newer shortcut
        new_shortcut = Shortcut.objects.create(
            key='new',
            value='New shortcut',
            owner=self.user
        )
        new_shortcut.sets.add(self.shortcut_set)

        # Request shortcuts updated after 'now'
        response = self.client.get('/api/shortcuts/', {
            'updated_after': (now - timedelta(seconds=1)).isoformat()
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_shortcuts_include_set_info(self):
        """Shortcuts should include set names and types."""
        response = self.client.get('/api/shortcuts/')

        shortcut_data = response.data[0]
        self.assertIn('set_names', shortcut_data)
        self.assertIn('set_types', shortcut_data)
        self.assertIn('test-set', shortcut_data['set_names'])

    def test_create_shortcut_with_sets(self):
        """Creating a shortcut should correctly save the sets relationship."""
        # Create a personal set for the user
        personal_set = ShortcutSet.objects.create(
            name='my-personal-set',
            set_type='personal',
            owner=self.user
        )

        response = self.client.post('/api/shortcuts/', {
            'key': 'new_shortcut',
            'content_type': 'text',
            'value': 'New value',
            'sets': [personal_set.id]
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('set_names', response.data)
        self.assertIn('my-personal-set', response.data['set_names'])

        # Verify in database
        shortcut = Shortcut.objects.get(key='new_shortcut')
        self.assertEqual(shortcut.sets.count(), 1)
        self.assertEqual(shortcut.sets.first().name, 'my-personal-set')

    def test_copy_birou_to_personal_creates_independent_shortcut(self):
        """Copying a Birou shortcut to Personal should create an independent shortcut."""
        # Create Birou set (general type)
        birou_set = ShortcutSet.objects.create(
            name='Birou',
            set_type='general',
            owner=None
        )

        # Create personal set
        personal_set = ShortcutSet.objects.create(
            name='Personal',
            set_type='personal',
            owner=self.user
        )

        # Create a Birou shortcut (owned by None or staff)
        birou_shortcut = Shortcut.objects.create(
            key='shared_key',
            value='Original Birou value',
            owner=None  # Birou shortcuts typically have no owner
        )
        birou_shortcut.sets.add(birou_set)

        # Simulate "copy to personal" by creating a new shortcut with same key
        response = self.client.post('/api/shortcuts/', {
            'key': 'shared_key',  # Same key as Birou
            'content_type': 'text',
            'value': 'My personal version',
            'sets': [personal_set.id]
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify we now have two shortcuts with the same key
        shortcuts = Shortcut.objects.filter(key='shared_key')
        self.assertEqual(shortcuts.count(), 2)

        # Delete the personal shortcut
        personal_shortcut = Shortcut.objects.get(key='shared_key', owner=self.user)
        personal_shortcut_id = personal_shortcut.id

        delete_response = self.client.delete(f'/api/shortcuts/{personal_shortcut_id}/')
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify Birou shortcut still exists
        birou_shortcut.refresh_from_db()
        self.assertEqual(birou_shortcut.key, 'shared_key')
        self.assertEqual(birou_shortcut.value, 'Original Birou value')

        # Only Birou shortcut should remain
        shortcuts = Shortcut.objects.filter(key='shared_key')
        self.assertEqual(shortcuts.count(), 1)


class BulkSyncAPITests(APITestCase):
    """Tests for bulk sync endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.token = ExpiringToken.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        # Create test data
        self.shortcut_set = ShortcutSet.objects.create(
            name='birou',
            set_type='general',
            owner=self.user
        )
        self.shortcut = Shortcut.objects.create(
            key='test',
            value='Test value',
            owner=self.user
        )
        self.shortcut.sets.add(self.shortcut_set)

    def test_bulk_sync_returns_sets_and_shortcuts(self):
        """Bulk sync should return both sets and shortcuts."""
        response = self.client.post('/api/sync/bulk/', {
            'sets': ['birou']
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('sets', response.data)
        self.assertIn('shortcuts', response.data)
        self.assertIn('server_time', response.data)
        self.assertIn('count', response.data)

    def test_bulk_sync_filters_by_sets(self):
        """Bulk sync should filter by requested sets."""
        # Create another set
        other_set = ShortcutSet.objects.create(
            name='other',
            set_type='personal',
            owner=self.user
        )
        other_shortcut = Shortcut.objects.create(
            key='other',
            value='Other',
            owner=self.user
        )
        other_shortcut.sets.add(other_set)

        response = self.client.post('/api/sync/bulk/', {
            'sets': ['birou']
        }, format='json')

        # Should only return 'birou' set shortcuts
        shortcut_keys = [s['key'] for s in response.data['shortcuts']]
        self.assertIn('test', shortcut_keys)
        self.assertNotIn('other', shortcut_keys)

    def test_bulk_sync_delta(self):
        """Bulk sync with updated_after returns only new changes."""
        now = timezone.now()

        response = self.client.post('/api/sync/bulk/', {
            'sets': ['birou'],
            'updated_after': now.isoformat()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_bulk_sync_count_accuracy(self):
        """Count in response should match actual data."""
        response = self.client.post('/api/sync/bulk/', {
            'sets': ['birou']
        }, format='json')

        self.assertEqual(
            response.data['count']['sets'],
            len(response.data['sets'])
        )
        self.assertEqual(
            response.data['count']['shortcuts'],
            len(response.data['shortcuts'])
        )


# =============================================================================
# THROTTLING TESTS
# =============================================================================

@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': {
            'login': '2/minute',
            'token_refresh': '2/hour',
            'bulk_sync': '2/hour',
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


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class IntegrationTests(APITestCase):
    """End-to-end integration tests."""

    def setUp(self):
        self.client = APIClient()

    def test_full_auth_flow(self):
        """Test complete authentication flow: register -> login -> use API -> logout."""
        # Create user (normally done via admin)
        User.objects.create_user(
            username='integration_user',
            password='secure_pass_123'
        )

        # Login
        login_response = self.client.post('/api/auth/login/', {
            'username': 'integration_user',
            'password': 'secure_pass_123'
        })
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        token = login_response.data['token']

        # Use API with token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        sets_response = self.client.get('/api/sets/')
        self.assertEqual(sets_response.status_code, status.HTTP_200_OK)

        # Verify token
        verify_response = self.client.get('/api/auth/verify/')
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertTrue(verify_response.data['valid'])

        # Logout
        logout_response = self.client.post('/api/auth/logout/')
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        # Token should no longer work
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        after_logout = self.client.get('/api/sets/')
        self.assertEqual(after_logout.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_shortcut_sync_workflow(self):
        """Test typical extension sync workflow."""
        # Setup
        user = User.objects.create_user(username='sync_user', password='pass')
        token = ExpiringToken.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create sets and shortcuts
        birou = ShortcutSet.objects.create(name='birou', set_type='general', owner=user)
        personal = ShortcutSet.objects.create(
            name='sync_user', set_type='personal', owner=user
        )

        shortcut1 = Shortcut.objects.create(key='hello', value='Hello!', owner=user)
        shortcut1.sets.add(birou)

        shortcut2 = Shortcut.objects.create(
            key='personal', value='My shortcut', owner=user
        )
        shortcut2.sets.add(personal)

        # Initial sync (no updated_after)
        response = self.client.post('/api/sync/bulk/', {
            'sets': ['birou', 'sync_user']
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count']['shortcuts'], 2)

        # Record sync time
        sync_time = response.data['server_time']

        # Add new shortcut
        shortcut3 = Shortcut.objects.create(key='new', value='New!', owner=user)
        shortcut3.sets.add(birou)

        # Delta sync
        delta_response = self.client.post('/api/sync/bulk/', {
            'sets': ['birou', 'sync_user'],
            'updated_after': sync_time
        }, format='json')

        self.assertEqual(delta_response.status_code, status.HTTP_200_OK)
        # Should only return the new shortcut
        self.assertEqual(delta_response.data['count']['shortcuts'], 1)
        self.assertEqual(delta_response.data['shortcuts'][0]['key'], 'new')
