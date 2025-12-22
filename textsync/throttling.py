"""
Custom throttling classes for AutoText API.

Provides endpoint-specific rate limiting for security-sensitive operations.
"""
from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """
    Rate limit login attempts to prevent brute force attacks.
    Uses IP address as the identifier.
    """
    scope = 'login'

    def get_cache_key(self, request, view):
        # Use IP address for anonymous login attempts
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class TokenRefreshRateThrottle(SimpleRateThrottle):
    """
    Rate limit token refresh to prevent token churn attacks.
    Uses user ID as the identifier.
    """
    scope = 'token_refresh'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class BulkSyncRateThrottle(SimpleRateThrottle):
    """
    Rate limit bulk sync operations as they are resource-intensive.
    Uses user ID as the identifier.
    """
    scope = 'bulk_sync'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
