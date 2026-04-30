from django.apps import AppConfig
from django.db.backends.signals import connection_created


def set_sqlite_pragmas(sender, connection, **kwargs):
    """Apply SQLite tuning pragmas on every new connection.

    WAL mode allows concurrent readers + 1 writer (vs default rollback journal
    that blocks the whole DB on write). synchronous=NORMAL is safe for
    non-critical data; foreign_keys=ON enforces referential integrity that
    SQLite leaves off by default.
    """
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA temp_store=MEMORY;")
        cursor.execute(
            "PRAGMA mmap_size=268435456;"
        )  # 256MB — right-sized for <50MB DB
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA wal_autocheckpoint=1000;")


class TextsyncConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "textsync"

    def ready(self):
        connection_created.connect(set_sqlite_pragmas)
        from . import signals  # noqa: F401
