#!/bin/bash
# Daily encrypted backup of the production AutoText DB.
#
# Deployment:
#   1. Copy this file to /home/cosmin/scripts/autotext-backup.sh on OVH.
#   2. chmod +x /home/cosmin/scripts/autotext-backup.sh
#   3. Generate an age key pair LOCALLY (NOT on OVH):
#        age-keygen -o ~/.ssh/age.key
#        chmod 600 ~/.ssh/age.key
#        cat ~/.ssh/age.key | grep public:  # copy the value
#   4. Edit AGE_PUBKEY below with that public key.
#   5. Add to crontab on OVH (`crontab -e`):
#        30 3 * * * /home/cosmin/scripts/autotext-backup.sh \
#          >> /home/cosmin/scripts/autotext-backup.log 2>&1
#
# Restore (on a trusted device that has the private key):
#   scp ovh:/home/cosmin/backups/autotext/autotext-2026-04-25.age /tmp/
#   age -d -i ~/.ssh/age.key /tmp/autotext-2026-04-25.age > /tmp/db.sqlite3
#   sqlite3 /tmp/db.sqlite3 'SELECT count(*) FROM textsync_shortcut;'
#
# Note: This is REDUNDANT with the in-git versioning of db.sqlite3 (the
# repo is private and the DB is committed). It exists for OVH disk-failure
# scenarios between two consecutive `git push` events.
set -euo pipefail

BACKUP_DIR=/home/cosmin/backups/autotext
DB=/home/cosmin/web/autotext.zua.ro/db.sqlite3
AGE_PUBKEY="age1...REPLACE_WITH_YOUR_PUBLIC_KEY..."

if [[ "$AGE_PUBKEY" == age1...REPLACE* ]]; then
  echo "ERROR: AGE_PUBKEY is still the placeholder. Edit this script first." >&2
  exit 1
fi

if [[ ! -f "$DB" ]]; then
  echo "ERROR: DB not found at $DB" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
TMP=$(mktemp /tmp/autotext-backup.XXXXXX.sqlite)
trap 'rm -f "$TMP"' EXIT

# Checkpoint WAL into main DB so the .backup file is a clean snapshot
# without needing the -wal/-shm sidecars.
sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE);"
sqlite3 "$DB" ".backup $TMP"

OUT="$BACKUP_DIR/autotext-$(date +%F).age"
age -r "$AGE_PUBKEY" -o "$OUT" "$TMP"

# 30-day retention
find "$BACKUP_DIR" -name 'autotext-*.age' -mtime +30 -delete

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) backup ok: $OUT ($(stat -c%s "$OUT") bytes)"
