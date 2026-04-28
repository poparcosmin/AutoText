#!/bin/bash
# pre-commit-corpus-guard.sh
# Blocks accidental commit of PII-containing research artifacts.
# Install: cp research/scripts/pre-commit-corpus-guard.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -euo pipefail

STAGED=$(git diff --cached --name-only --diff-filter=AM)

if [ -z "$STAGED" ]; then
  exit 0
fi

# 1. Hard block on corpus/, pii_mapping/, *.gpg, audit.log
PROHIBITED=$(echo "$STAGED" | grep -E "^research/corpus/|/pii_mapping/|\.gpg$|^research/audit\.log$" || true)

if [ -n "$PROHIBITED" ]; then
  echo "BLOCK pre-commit-corpus-guard: prohibited research artifacts in staged files"
  echo ""
  echo "Files attempted to commit:"
  echo "$PROHIBITED" | sed 's/^/  - /'
  echo ""
  echo "These files contain PII or PII-derivable data and MUST NOT be committed."
  echo "If you believe this is a false positive, unstage with: git reset HEAD <file>"
  exit 1
fi

# 2. Soft warning on PII patterns in staged content (non-corpus files)
# Romanian patterns: CIF (RO + 6-10 digits), IBAN (RO + 22 chars), mobile (07XXXXXXXX)
LEAK_DIFF=$(git diff --cached -U0 --diff-filter=AM -- ':!research/corpus/' ':!**/*.gpg' || true)

PII_HITS=""

# CIF format
CIF_HIT=$(echo "$LEAK_DIFF" | grep -E '^\+.*\bRO[0-9]{6,10}\b' | grep -v 'RO4807535\|<CIF' || true)
[ -n "$CIF_HIT" ] && PII_HITS="${PII_HITS}\n[CIF candidate]\n${CIF_HIT}"

# IBAN format
IBAN_HIT=$(echo "$LEAK_DIFF" | grep -E '^\+.*\bRO[0-9]{2}[A-Z]{4}[0-9A-Z]{16}\b' | grep -v '<IBAN' || true)
[ -n "$IBAN_HIT" ] && PII_HITS="${PII_HITS}\n[IBAN candidate]\n${IBAN_HIT}"

# Romanian mobile
PHONE_HIT=$(echo "$LEAK_DIFF" | grep -E '^\+.*\b07[0-9]{8}\b' | grep -v '0721697233\|0744667233\|<PHONE' || true)
[ -n "$PHONE_HIT" ] && PII_HITS="${PII_HITS}\n[Phone candidate]\n${PHONE_HIT}"

if [ -n "$PII_HITS" ]; then
  echo "WARN pre-commit-corpus-guard: possible PII leak in staged content"
  echo -e "$PII_HITS"
  echo ""
  echo "If these are pseudonymized tokens or public PAFF identifiers, OK to proceed."
  echo "If real PII, unstage with: git reset HEAD <file>"
  echo ""
  echo "Proceed with commit? [y/N]"
  if [ -t 0 ]; then
    read -r reply < /dev/tty
  else
    reply="n"
  fi
  if [ "$reply" != "y" ] && [ "$reply" != "Y" ]; then
    echo "Commit aborted."
    exit 1
  fi
fi

exit 0
