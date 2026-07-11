"""Global pytest configuration.

Force an in-process LocMemCache for every test so the suite never depends on a
running Redis (the production backend). Endpoint tests go through DRF throttling,
which reads the default cache; without this, a missing/slow Redis makes those
tests flaky and slow. This generalises the per-test override already used in
test_cache.py and test_health.py to the whole suite.

override_settings(CACHES=...) fires the setting_changed signal, which resets the
cache handlers so each test gets a fresh LocMemCache instance (no cross-test
throttle-counter leakage). The explicit clear() is belt-and-suspenders.
"""

import pytest
from django.core.cache import caches
from django.test import override_settings

_LOCMEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}


@pytest.fixture(autouse=True)
def _hermetic_cache():
    with override_settings(CACHES=_LOCMEM_CACHES):
        caches["default"].clear()
        yield
        caches["default"].clear()
