"""
Middleware for request logging and context binding.

Provides structured logging context for all requests, including:
- Request ID for tracing
- User information
- Request timing
"""

import time
import uuid
import structlog
from django.utils.deprecation import MiddlewareMixin


logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware that:
    1. Generates a unique request_id for tracing
    2. Binds user context to all logs in the request
    3. Logs request start/end with timing information
    """

    def process_request(self, request):
        """Called on each request before the view."""
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]
        request.request_id = request_id
        request._start_time = time.time()

        # Bind context that will be included in all logs during this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.path,
            method=request.method,
            ip=self._get_client_ip(request),
        )

        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Called after request but before view."""
        # Add user context once authentication has processed
        if hasattr(request, 'user') and request.user.is_authenticated:
            structlog.contextvars.bind_contextvars(
                user_id=request.user.id,
                username=request.user.username,
            )
        return None

    def process_response(self, request, response):
        """Called on each response."""
        # Calculate request duration
        duration_ms = 0
        if hasattr(request, '_start_time'):
            duration_ms = (time.time() - request._start_time) * 1000

        # Log request completion (only for API requests to reduce noise)
        if request.path.startswith('/api/'):
            log_level = 'info'
            if response.status_code >= 500:
                log_level = 'error'
            elif response.status_code >= 400:
                log_level = 'warning'

            getattr(logger, log_level)(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

        # Clear context for next request
        structlog.contextvars.clear_contextvars()

        # Add request ID header for client-side debugging
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id

        return response

    def process_exception(self, request, exception):
        """Called when a view raises an exception."""
        logger.exception(
            "request_exception",
            exception_type=type(exception).__name__,
            exception_message=str(exception),
        )
        return None

    @staticmethod
    def _get_client_ip(request):
        """Extract client IP, considering proxy headers."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
