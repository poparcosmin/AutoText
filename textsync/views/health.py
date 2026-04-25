"""Public meta endpoints — health check (API) and privacy policy (HTML)."""
import structlog
import time

from django.core.cache import cache
from django.db import connection
from django.shortcuts import render
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

logger = structlog.get_logger(__name__)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check_view(request):
    """
    Health check endpoint for monitoring and load balancers.

    GET /api/health/
    Returns: {
        "status": "healthy" | "degraded" | "unhealthy",
        "version": "1.0.0",
        "timestamp": "...",
        "checks": {
            "database": { "status": "ok", "latency_ms": 5 },
            "cache": { "status": "ok", "latency_ms": 2 }
        }
    }

    No authentication required - this endpoint is meant for:
    - Kubernetes liveness/readiness probes
    - Load balancer health checks
    - Monitoring systems (Prometheus, Datadog, etc.)
    """
    from django.conf import settings as django_settings

    checks = {}
    overall_status = "healthy"

    # Check database connectivity
    db_start = time.time()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_latency = (time.time() - db_start) * 1000
        checks['database'] = {
            'status': 'ok',
            'latency_ms': round(db_latency, 2)
        }
    except Exception as e:
        checks['database'] = {
            'status': 'error',
            'error': str(e)
        }
        overall_status = "unhealthy"
        logger.error(f"Health check - database error: {e}")

    # Check cache connectivity
    cache_start = time.time()
    try:
        test_key = "health_check_test"
        cache.set(test_key, "ok", timeout=10)
        result = cache.get(test_key)
        cache.delete(test_key)
        cache_latency = (time.time() - cache_start) * 1000

        if result == "ok":
            checks['cache'] = {
                'status': 'ok',
                'latency_ms': round(cache_latency, 2)
            }
        else:
            checks['cache'] = {
                'status': 'degraded',
                'error': 'Cache read/write failed'
            }
            if overall_status == "healthy":
                overall_status = "degraded"
    except Exception as e:
        checks['cache'] = {
            'status': 'error',
            'error': str(e)
        }
        # Cache failure is degraded, not unhealthy (app can function without cache)
        if overall_status == "healthy":
            overall_status = "degraded"
        logger.warning(f"Health check - cache error: {e}")

    # Get version from settings or default
    version = getattr(django_settings, 'APP_VERSION', '1.0.0')

    response_data = {
        'status': overall_status,
        'version': version,
        'timestamp': timezone.now().isoformat(),
        'checks': checks
    }

    # Return appropriate HTTP status code
    if overall_status == "unhealthy":
        return Response(response_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    elif overall_status == "degraded":
        return Response(response_data, status=status.HTTP_200_OK)  # Still operational
    else:
        return Response(response_data, status=status.HTTP_200_OK)


def privacy_view(request):
    """
    Privacy Policy page for Chrome Web Store compliance.
    """
    return render(request, 'privacy.html')


def help_view(request):
    """
    User-facing help & documentation page.

    Linked from the Chrome Web Store listing as the support URL — Chrome
    requires that link to resolve to a 200 page during review. Static
    template, no auth: meant for end-users (Romanian-language).
    """
    return render(request, 'help.html')
