"""
Cache utilities for AutoText API.

Provides cache key helpers and invalidation for shortcuts and sets.
Uses Redis with graceful degradation when unavailable.
"""

from django.core.cache import cache


def get_cache_key(prefix: str, *args) -> str:
    """Generate a consistent cache key."""
    parts = [prefix] + [str(arg) for arg in args if arg is not None]
    return ":".join(parts)


def get_user_shortcuts_key(user_id: int) -> str:
    """Cache key for user's shortcuts."""
    return get_cache_key("user_shortcuts", user_id)


def get_user_sets_key(user_id: int) -> str:
    """Cache key for user's shortcut sets."""
    return get_cache_key("user_sets", user_id)


def get_shortcut_key(shortcut_id: int) -> str:
    """Cache key for a single shortcut."""
    return get_cache_key("shortcut", shortcut_id)


def invalidate_user_cache(user_id: int) -> None:
    """Invalidate all cache entries for a user.

    Covers: user_shortcuts:<id>, user_shortcuts:<id>:<sets_param> variants,
    user_sets:<id>, bulk_sync:<id>:<sets_key> variants.

    Uses django-redis delete_pattern when available; falls back to explicit
    keys for backends that lack pattern support (e.g. LocMemCache in tests).
    """
    # Base keys — always present (what the legacy test asserts against)
    base_keys = [
        get_user_shortcuts_key(user_id),
        get_user_sets_key(user_id),
    ]
    cache.delete_many(base_keys)

    # Variant keys set by viewsets with sets_param suffix and bulk_sync
    delete_pattern = getattr(cache, "delete_pattern", None)
    if callable(delete_pattern):
        delete_pattern(f"{get_user_shortcuts_key(user_id)}:*")
        delete_pattern(f"bulk_sync:{user_id}:*")


