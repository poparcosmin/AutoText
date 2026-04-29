#!/usr/bin/env python
"""Post-deploy verification — sanity-checks production state matches local."""
import os
import sys
from pathlib import Path

# Bootstrap Django
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from textsync.models import Shortcut, ShortcutSet, UserVariable  # noqa: E402

EXPECTED_TOTAL = 85
EXPECTED_VARIABLES = 48
EXPECTED_ATOMIC = [
    "salut", "mts", "mts_short", "cta-mod", "cta-primire", "reply-yn",
    "eta-curier", "eta-paff", "sig-personal", "sig-equipe", "sig-short",
    "track-fan", "track-dragon", "confirm-plata", "tranzitie-pleaca",
    "tranzitie-pleaca-buc", "promise-awb", "closing",
]
EXPECTED_FOLLOWUP = [
    "op-fu1", "op-fu2", "op-fu3", "op-accept", "op-rej",
    "proba", "urg", "ret",
]
EXPECTED_SUBJECT = [
    "subj-op", "subj-mc1", "subj-mp1", "subj-ffd", "subj-ffan",
    "subj-nu1", "subj-fu1", "subj-fu3",
]


def check(label: str, actual, expected, *, exact: bool = True) -> bool:
    ok = (actual == expected) if exact else (actual >= expected)
    icon = "✓" if ok else "✗"
    note = "" if ok else f" (expected {expected})"
    print(f"  {icon} {label}: {actual}{note}")
    return ok


def check_keys(label: str, expected_keys: list[str]) -> bool:
    actual_keys = set(Shortcut.objects.filter(key__in=expected_keys).values_list("key", flat=True))
    missing = sorted(set(expected_keys) - actual_keys)
    if missing:
        print(f"  ✗ {label}: missing {len(missing)} → {missing}")
        return False
    print(f"  ✓ {label}: all {len(expected_keys)} present")
    return True


def main():
    print("=== AutoText production verification ===")
    print()
    print("Counts:")
    all_ok = True
    all_ok &= check("Total shortcuts", Shortcut.objects.count(), EXPECTED_TOTAL)
    all_ok &= check("User variables", UserVariable.objects.count(), EXPECTED_VARIABLES)
    all_ok &= check(
        "Shortcuts with variants",
        Shortcut.objects.exclude(variants=[]).count(),
        15,
        exact=False,
    )

    print()
    print("Atomic snippets (used via [[%s(...)]]):")
    all_ok &= check_keys("atomic snippets", EXPECTED_ATOMIC)

    print()
    print("Follow-up shortcuts (Layer 1):")
    all_ok &= check_keys("follow-up bodies", EXPECTED_FOLLOWUP)

    print()
    print("Subject line shortcuts (Layer 2):")
    all_ok &= check_keys("subject lines", EXPECTED_SUBJECT)

    print()
    print("Schema check:")
    try:
        # If variants column missing, this raises
        first = Shortcut.objects.first()
        _ = first.variants if first else None
        print("  ✓ variants column accessible")
    except Exception as e:
        print(f"  ✗ variants column issue: {e}")
        all_ok = False

    print()
    print("Per-user signature variables (sample check on first user):")
    from django.contrib.auth import get_user_model
    User = get_user_model()
    for username in ["aura", "bogdan", "cosmin", "florian"]:
        user = User.objects.filter(username=username).first()
        if not user:
            print(f"  ⚠ user '{username}' not found — skipped")
            continue
        my_name = UserVariable.objects.filter(user=user, name="my_name").first()
        my_phone = UserVariable.objects.filter(user=user, name="my_phone").first()
        marker = "✓" if my_name and my_phone else "✗"
        print(f"  {marker} {username}: my_name={my_name.value if my_name else 'MISSING'}, "
              f"my_phone={my_phone.value if my_phone else 'MISSING'}")
        if not (my_name and my_phone):
            all_ok = False

    print()
    print("Sample shortcut content check (mj2 should have form placeholders):")
    mj2 = Shortcut.objects.filter(key="mj2").first()
    if mj2 and "{{data:" in mj2.value:
        print("  ✓ mj2 contains form placeholder {{data:...}}")
    else:
        print(f"  ✗ mj2 missing or no form placeholder. Value head: {mj2.value[:80] if mj2 else 'NOT FOUND'}...")
        all_ok = False

    print()
    if all_ok:
        print("✅ ALL CHECKS PASSED — deploy is healthy")
        sys.exit(0)
    else:
        print("❌ SOME CHECKS FAILED — review output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
