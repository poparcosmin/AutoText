"""Tests for input validators and HTML sanitization."""

from django.test import TestCase

from ..validators import (
    sanitize_html,
    validate_shortcut_key,
    validate_shortcut_value,
    validate_set_name,
)


class ValidatorTests(TestCase):
    """Tests for input validators."""

    def test_validate_shortcut_key_valid(self):
        """Valid keys should pass."""
        valid_keys = ["hello", "my_key", "key-123", "key.name", "_private"]

        for key in valid_keys:
            is_valid, error = validate_shortcut_key(key)
            self.assertTrue(is_valid, f"Key '{key}' should be valid: {error}")

    def test_validate_shortcut_key_invalid_start_number(self):
        """Keys starting with number should fail."""
        is_valid, error = validate_shortcut_key("123key")
        self.assertFalse(is_valid)
        self.assertIn("start with", error.lower())

    def test_validate_shortcut_key_invalid_spaces(self):
        """Keys with spaces should fail."""
        is_valid, error = validate_shortcut_key("hello world")
        self.assertFalse(is_valid)

    def test_validate_shortcut_key_empty(self):
        """Empty key should fail."""
        is_valid, error = validate_shortcut_key("")
        self.assertFalse(is_valid)
        self.assertIn("required", error.lower())

    def test_validate_shortcut_key_too_long(self):
        """Key over 50 chars should fail."""
        long_key = "a" * 51
        is_valid, error = validate_shortcut_key(long_key)
        self.assertFalse(is_valid)
        self.assertIn("50", error)

    def test_validate_shortcut_value_valid(self):
        """Normal values should pass."""
        is_valid, error = validate_shortcut_value("Hello, World!")
        self.assertTrue(is_valid)

    def test_validate_shortcut_value_empty(self):
        """Empty value should be valid (HTML might be used instead)."""
        is_valid, error = validate_shortcut_value("")
        self.assertTrue(is_valid)

    def test_validate_shortcut_value_too_long(self):
        """Value over max length should fail."""
        long_value = "a" * 50001
        is_valid, error = validate_shortcut_value(long_value)
        self.assertFalse(is_valid)

    def test_validate_set_name_valid(self):
        """Valid set names should pass."""
        valid_names = ["birou", "My Set", "set-123", "set_name"]

        for name in valid_names:
            is_valid, error = validate_set_name(name)
            self.assertTrue(is_valid, f"Name '{name}' should be valid: {error}")

    def test_validate_set_name_empty(self):
        """Empty name should fail."""
        is_valid, error = validate_set_name("")
        self.assertFalse(is_valid)

    def test_validate_set_name_special_chars(self):
        """Special characters should fail."""
        is_valid, error = validate_set_name("set@name!")
        self.assertFalse(is_valid)


class HTMLSanitizationTests(TestCase):
    """Tests for HTML sanitization."""

    def test_sanitize_allowed_tags(self):
        """Allowed tags should be preserved."""
        html = "<p><strong>Bold</strong> and <em>italic</em></p>"
        result = sanitize_html(html)

        self.assertIn("<strong>", result)
        self.assertIn("<em>", result)
        self.assertIn("<p>", result)

    def test_sanitize_script_removed(self):
        """Script tags should be removed."""
        html = '<p>Hello</p><script>alert("xss")</script>'
        result = sanitize_html(html)

        self.assertNotIn("<script>", result)
        self.assertNotIn("alert", result)

    def test_sanitize_onclick_removed(self):
        """Event handlers should be removed."""
        html = '<button onclick="alert(1)">Click</button>'
        result = sanitize_html(html)

        self.assertNotIn("onclick", result)

    def test_sanitize_javascript_href_removed(self):
        """javascript: URLs should be removed."""
        html = '<a href="javascript:alert(1)">Link</a>'
        result = sanitize_html(html)

        self.assertNotIn("javascript:", result)

    def test_sanitize_preserves_safe_href(self):
        """Safe URLs should be preserved."""
        html = '<a href="https://example.com">Link</a>'
        result = sanitize_html(html)

        self.assertIn("https://example.com", result)

    def test_sanitize_empty_input(self):
        """Empty input should return empty."""
        self.assertEqual(sanitize_html(""), "")
        self.assertIsNone(sanitize_html(None))
