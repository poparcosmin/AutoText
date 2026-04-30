"""Dry-run audit: report which Shortcut.html_value rows would be modified
when ShortcutSerializer.validate_html_value starts calling sanitize_html.

Uses raw SQL through Django's connection so it works against any historical
schema variant — local dev DB sometimes lags prod (owner_id/usage_count
weren't always there). We only need id/key/html_value, which have existed
since 0001.

Run before deploying Wave 3.1 to make sure the bleach allowlist in
textsync/validators.py is permissive enough for the actual content.

Usage:
    uv run python scripts/audit_html_shortcuts.py
"""

import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import connection  # noqa: E402

from textsync.validators import sanitize_html  # noqa: E402


def audit():
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM textsync_shortcut")
        total_all = cursor.fetchone()[0]

        cursor.execute(
            "SELECT id, key, html_value FROM textsync_shortcut "
            "WHERE html_value IS NOT NULL AND html_value != ''"
        )
        rows = cursor.fetchall()

    total_with_html = len(rows)
    modified = []
    for row_id, key, html_value in rows:
        cleaned = sanitize_html(html_value)
        if cleaned != html_value:
            modified.append(
                {
                    "id": row_id,
                    "key": key,
                    "before_len": len(html_value),
                    "after_len": len(cleaned),
                    "delta": len(html_value) - len(cleaned),
                }
            )

    print(f"Total shortcuts: {total_all}")
    print(f"  With html_value: {total_with_html}")
    print(f"  Will be modified: {len(modified)}")
    if total_with_html:
        pct = 100.0 * len(modified) / total_with_html
        print(f"  Affected ratio: {pct:.1f}%")

    if not modified:
        print("\nNo changes — safe to deploy validate_html_value.")
        return 0

    print("\nFirst 20 affected entries:")
    for m in modified[:20]:
        print(
            f"  id={m['id']:>4}  key={m['key']:<20}  "
            f"{m['before_len']:>5} -> {m['after_len']:<5} "
            f"(strip {m['delta']} chars)"
        )

    if len(modified) > 20:
        print(f"  ... and {len(modified) - 20} more")

    print("\nRecommendation:")
    pct = 100.0 * len(modified) / total_with_html if total_with_html else 0
    if pct < 5:
        print("  <5% affected — likely benign (script tags, on* handlers).")
        print("  Spot-check a few entries; deploy if no real content lost.")
    elif pct < 20:
        print("  5-20% affected — review the diffs before deploy.")
        print("  May need to widen ALLOWED_TAGS or ALLOWED_ATTRIBUTES.")
    else:
        print("  >20% affected — DO NOT deploy without a fix.")
        print("  Allowlist is probably too narrow for legitimate content.")

    return 0


if __name__ == "__main__":
    sys.exit(audit())
