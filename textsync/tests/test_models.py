"""Tests for models: ExpiringToken, ShortcutSet, Shortcut."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from ..models import ExpiringToken, Shortcut, ShortcutSet


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
