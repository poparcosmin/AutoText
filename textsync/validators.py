"""
Input validation and sanitization utilities for AutoText.

Uses bleach library to clean HTML and prevent XSS attacks.
"""
import re
import bleach


# Allowed HTML tags for rich text shortcuts
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'strike',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li',
    'a', 'span', 'div',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'blockquote', 'pre', 'code',
    'img', 'hr',
]

# Allowed attributes per tag
ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style'],
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
    'span': ['data-placeholder'],  # For TinyMCE placeholders
}

# Allowed CSS properties in style attribute
ALLOWED_STYLES = [
    'color', 'background-color', 'font-size', 'font-weight', 'font-style',
    'text-align', 'text-decoration', 'margin', 'padding',
    'margin-left', 'margin-right', 'margin-top', 'margin-bottom',
    'padding-left', 'padding-right', 'padding-top', 'padding-bottom',
    'border', 'border-color', 'border-width', 'border-style',
    'width', 'height', 'max-width', 'max-height',
]

# Allowed URL protocols
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto', 'tel']


def sanitize_html(html_content: str) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.

    Args:
        html_content: Raw HTML string from user input

    Returns:
        Sanitized HTML string safe for display
    """
    if not html_content:
        return html_content

    # First, remove dangerous tags AND their content entirely
    # bleach.clean with strip=True only removes tags, not content
    dangerous_tags_pattern = re.compile(
        r'<(script|style|noscript|iframe|object|embed|applet)[^>]*>.*?</\1>',
        re.IGNORECASE | re.DOTALL
    )
    html_content = dangerous_tags_pattern.sub('', html_content)

    # Also remove self-closing/unclosed dangerous tags
    html_content = re.sub(r'<(script|style|noscript|iframe|object|embed|applet)[^>]*/?>',
                          '', html_content, flags=re.IGNORECASE)

    # Use bleach to clean the remaining HTML
    cleaned = bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,  # Strip disallowed tags instead of escaping
    )

    return cleaned


def validate_shortcut_key(key: str) -> tuple[bool, str]:
    """
    Validate a shortcut key.

    Rules:
    - Must be 1-50 characters
    - Can contain alphanumeric, underscore, hyphen, period
    - Cannot start with a number
    - Cannot contain spaces

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not key:
        return False, "Shortcut key is required"

    if len(key) > 50:
        return False, "Shortcut key must be 50 characters or less"

    if len(key) < 1:
        return False, "Shortcut key must be at least 1 character"

    # Check for valid characters
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_\-\.]*$'
    if not re.match(pattern, key):
        return False, "Shortcut key must start with a letter or underscore and contain only alphanumeric characters, underscores, hyphens, or periods"

    return True, ""


def validate_shortcut_value(value: str, max_length: int = 50000) -> tuple[bool, str]:
    """
    Validate a shortcut value (plain text).

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value:
        return True, ""  # Empty value is allowed (HTML might be set instead)

    if len(value) > max_length:
        return False, f"Shortcut value must be {max_length} characters or less"

    return True, ""


def validate_set_name(name: str) -> tuple[bool, str]:
    """
    Validate a shortcut set name.

    Rules:
    - Must be 1-50 characters
    - Can contain alphanumeric, spaces, underscores, hyphens

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Set name is required"

    if len(name) > 50:
        return False, "Set name must be 50 characters or less"

    if len(name) < 1:
        return False, "Set name must be at least 1 character"

    # Check for valid characters
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9\s_\-]*$'
    if not re.match(pattern, name):
        return False, "Set name must start with an alphanumeric character and contain only letters, numbers, spaces, underscores, or hyphens"

    return True, ""
