#!/bin/bash
# Apply textsync data dump to production DB.
# Run AFTER `git pull origin main` and `manage.py migrate textsync`.
#
# Strategy: idempotent — truncates only the 3 textsync tables we ship,
# then loaddata. Preserves expiringtoken (auth tokens stay alive per user).

set -euo pipefail

cd "$(dirname "$0")/.."  # cd to project root (one up from bundle/)

PYTHON=".venv/bin/python"
DUMP_FILE="$(dirname "$0")/textsync_data.json"

if [[ ! -f "$DUMP_FILE" ]]; then
    echo "ERROR: textsync_data.json not found at $DUMP_FILE"
    exit 1
fi

echo "=== Pre-flight: current state ==="
$PYTHON -c "
import django
django.setup()
" 2>/dev/null || $PYTHON manage.py check

CURRENT_COUNT=$($PYTHON manage.py shell -c "
from textsync.models import Shortcut
print(Shortcut.objects.count())
" 2>/dev/null | tail -1)
echo "  Current shortcuts in DB: $CURRENT_COUNT"

read -p "Apply 137-object dump? Will TRUNCATE+REPLACE shortcuts/uservariables/shortcutsets. [y/N] " yn
if [[ "$yn" != "y" && "$yn" != "Y" ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "=== Step 1: Truncate target tables (preserve expiringtoken) ==="
$PYTHON manage.py shell -c "
from textsync.models import Shortcut, ShortcutSet, UserVariable
print(f'Deleting {Shortcut.objects.count()} shortcuts...')
Shortcut.objects.all().delete()
print(f'Deleting {UserVariable.objects.count()} user variables...')
UserVariable.objects.all().delete()
print(f'Deleting {ShortcutSet.objects.count()} shortcut sets...')
ShortcutSet.objects.all().delete()
print('Truncate complete.')
"

echo ""
echo "=== Step 2: Load data from dump ==="
$PYTHON manage.py loaddata "$DUMP_FILE"

echo ""
echo "=== Step 3: Sanity check ==="
$PYTHON manage.py shell -c "
from textsync.models import Shortcut, ShortcutSet, UserVariable
from django.contrib.auth import get_user_model
User = get_user_model()
print(f'Shortcuts: {Shortcut.objects.count()}')
print(f'  with variants: {Shortcut.objects.exclude(variants=[]).count()}')
print(f'Shortcut sets: {ShortcutSet.objects.count()}')
print(f'User variables: {UserVariable.objects.count()}')
print(f'Active users: {User.objects.filter(is_active=True).count()}')
print()
print('Atomic snippets present:')
for k in ['salut', 'mts', 'eta-curier', 'sig-personal', 'reply-yn', 'confirm-plata']:
    exists = Shortcut.objects.filter(key=k).exists()
    print(f'  {k}: {\"✓\" if exists else \"✗\"}')
"

echo ""
echo "✓ Apply complete. Restart Django service to pick up cache changes."
echo "  sudo systemctl restart autotext"
echo ""
echo "Then ask Aura/Bogdan/Florian to click 'Sync Now' in extension popup."
