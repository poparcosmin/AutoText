"""
Cache utilities for AutoText API.

Provides cache decorators and helpers for shortcuts and sets.
Uses Redis with graceful degradation when unavailable.
"""

from functools import wraps
from django.core.cache import cache
from django.conf import settings


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


def cached_shortcuts(timeout: int | None = None):
    """
    Decorator to cache shortcut queries per user.

    Usage:
        @cached_shortcuts(timeout=300)
        def get_user_shortcuts(user):
            ...
    """
    if timeout is None:
        timeout = getattr(settings, "CACHE_TIMEOUTS", {}).get("shortcuts", 300)

    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Skip cache for non-GET requests or when updated_after is used
            if request.method != "GET":
                return func(self, request, *args, **kwargs)

            updated_after = request.query_params.get("updated_after")
            if updated_after:
                # Delta sync - don't cache partial results
                return func(self, request, *args, **kwargs)

            cache_key = get_user_shortcuts_key(request.user.id)
            cached_data = cache.get(cache_key)

            if cached_data is not None:
                return cached_data

            response = func(self, request, *args, **kwargs)

            # Only cache successful responses
            if hasattr(response, "status_code") and response.status_code == 200:
                cache.set(cache_key, response, timeout)

            return response

        return wrapper

    return decorator


def cached_sets(timeout: int | None = None):
    """
    Decorator to cache shortcut sets queries per user.
    """
    if timeout is None:
        timeout = getattr(settings, "CACHE_TIMEOUTS", {}).get("shortcut_sets", 600)

    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if request.method != "GET":
                return func(self, request, *args, **kwargs)

            cache_key = get_user_sets_key(request.user.id)
            cached_data = cache.get(cache_key)

            if cached_data is not None:
                return cached_data

            response = func(self, request, *args, **kwargs)

            if hasattr(response, "status_code") and response.status_code == 200:
                cache.set(cache_key, response, timeout)

            return response

        return wrapper

    return decorator
