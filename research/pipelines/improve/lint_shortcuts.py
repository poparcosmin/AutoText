"""
Lint shortcuts in the AutoText DB.

Detectează:
  1. Hardcoded years (alert dacă apare un an < anul curent în primary/variants)
  2. Lipsă diacritice ("Buna", "Va multumim", "soferul" etc.)
  3. [[var:NAME]] cu nume care NU există ca user_variable pentru NICIUN user
  4. [[%s(target)]] cu target care nu există ca shortcut
  5. Form placeholders cu sintaxă invalidă ({{name}} fără label/default)
  6. Variants JSON malformed
  7. Cursor marker duplicat ($|$ apare de >1× în același text)

Usage:
  uv run python research/pipelines/improve/lint_shortcuts.py
  uv run python research/pipelines/improve/lint_shortcuts.py --json   # for CI

Exit code:
  0 — no issues
  1 — warnings only
  2 — errors (hardcoded year, broken refs)
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

DB = Path(__file__).resolve().parents[3] / "db.sqlite3"

CURRENT_YEAR = datetime.now().year

# Words that should always have diacritics in PAFF Romanian
NON_DIACRITIC_PATTERNS = {
    r"\bBuna\b": "Bună",
    r"\bbuna\b": "bună",
    r"\bVa multumim\b": "Vă mulțumim",
    r"\bsoferul\b": "șoferul",
    r"\bSoferul\b": "Șoferul",
    r"\bPuteti\b": "Puteți",
    r"\bputeti\b": "puteți",
    r"\bsi\b": "și",
    r"\bSi\b": "Și",
    r"\bnumarul\b": "numărul",
    r"\bMulţumim\b": "Mulțumim",  # ţ vs ț
}


class Issue(NamedTuple):
    severity: str  # "ERROR" | "WARN" | "INFO"
    shortcut: str
    location: str  # "primary" | "variant 1" | "variant 2" | "user_var:NAME"
    rule: str
    detail: str


def lint_text(
    text: str, sc_key: str, location: str, all_keys: set[str], all_var_names: set[str]
) -> list[Issue]:
    issues: list[Issue] = []
    if not text:
        return issues

    # 1. Hardcoded year < current year
    for match in re.finditer(r"\b(20[1-2][0-9])\b", text):
        year = int(match.group(1))
        if year < CURRENT_YEAR:
            issues.append(
                Issue(
                    "ERROR",
                    sc_key,
                    location,
                    "hardcoded-stale-year",
                    f"Found year {year} (current: {CURRENT_YEAR}). Replace with placeholder.",
                )
            )

    # 2. Lipsă diacritice (skip case where text is in plain ASCII intentionally
    # — only flag if SOME diacritics exist elsewhere in the same text)
    has_diacritics = bool(re.search(r"[ăâîșțĂÂÎȘȚ]", text))
    if has_diacritics:
        for pattern, suggestion in NON_DIACRITIC_PATTERNS.items():
            match_diag = re.search(pattern, text)
            if match_diag:
                issues.append(
                    Issue(
                        "WARN",
                        sc_key,
                        location,
                        "missing-diacritics",
                        f"Found '{match_diag.group(0)}' — should be '{suggestion}'.",
                    )
                )

    # 3. [[var:NAME]] referencing a name that exists for NO user
    for match in re.finditer(r"\[\[var:([^\]]+)\]\]", text):
        name = match.group(1).strip()
        if name not in all_var_names:
            issues.append(
                Issue(
                    "ERROR",
                    sc_key,
                    location,
                    "broken-var-ref",
                    f"[[var:{name}]] but no user_variable named '{name}' exists.",
                )
            )

    # 4. [[%s(target)]] with non-existent target
    for match in re.finditer(r"\[\[%s\(([^)]+)\)\]\]", text):
        target = match.group(1).strip()
        if target not in all_keys:
            issues.append(
                Issue(
                    "ERROR",
                    sc_key,
                    location,
                    "broken-nesting-ref",
                    f"[[%s({target})]] but no shortcut with key '{target}' exists.",
                )
            )

    # 5. Form placeholders with invalid syntax
    # Valid: {{name}}, {{name:Label}}, {{name:Label|default}}
    for match in re.finditer(r"\{\{([^}]+)\}\}", text):
        body = match.group(1)
        # Must have at least a name without spaces
        name = body.split(":")[0].strip()
        if not name or " " in name:
            issues.append(
                Issue(
                    "WARN",
                    sc_key,
                    location,
                    "form-placeholder-syntax",
                    f"Suspect form placeholder: {{{{ {body} }}}}. Expected {{name:Label|default}}.",
                )
            )

    # 7. Cursor marker $|$ duplicated
    cursor_count = text.count("$|$")
    if cursor_count > 1:
        issues.append(
            Issue(
                "WARN",
                sc_key,
                location,
                "duplicate-cursor",
                f"$|$ appears {cursor_count} times — only the first lands cursor.",
            )
        )

    return issues


def lint_db() -> list[Issue]:
    issues: list[Issue] = []
    con = sqlite3.connect(DB)

    # Load all shortcut keys for nesting validation
    cur = con.execute(
        "SELECT key, value, COALESCE(variants, '[]') FROM textsync_shortcut;"
    )
    rows = list(cur.fetchall())
    all_keys = {row[0] for row in rows}

    # Load all user_variable names (union across users — a variable is "valid"
    # if at least one user has it; per-user resolution still happens at expand)
    cur = con.execute("SELECT DISTINCT name FROM textsync_uservariable;")
    all_var_names = {row[0] for row in cur.fetchall()}

    for key, value, variants_json in rows:
        # 6. Variants JSON malformed
        try:
            variants = json.loads(variants_json) if variants_json else []
            if not isinstance(variants, list):
                issues.append(
                    Issue(
                        "ERROR",
                        key,
                        "variants",
                        "variants-not-list",
                        f"variants is not a JSON array (got {type(variants).__name__}).",
                    )
                )
                variants = []
        except json.JSONDecodeError as e:
            issues.append(
                Issue(
                    "ERROR",
                    key,
                    "variants",
                    "variants-json-invalid",
                    f"variants JSON parse error: {e}",
                )
            )
            variants = []

        # Lint primary
        issues.extend(lint_text(value, key, "primary", all_keys, all_var_names))

        # Lint variants
        for i, v in enumerate(variants):
            issues.extend(lint_text(v, key, f"variant {i+1}", all_keys, all_var_names))

    con.close()
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Output JSON for CI")
    parser.add_argument(
        "--severity",
        choices=["ERROR", "WARN", "INFO"],
        default="WARN",
        help="Minimum severity to report (default: WARN)",
    )
    args = parser.parse_args()

    threshold = {"ERROR": 0, "WARN": 1, "INFO": 2}[args.severity]
    severity_rank = {"ERROR": 0, "WARN": 1, "INFO": 2}

    all_issues = lint_db()
    filtered = [i for i in all_issues if severity_rank[i.severity] <= threshold]

    if args.json:
        print(json.dumps([i._asdict() for i in filtered], indent=2, ensure_ascii=False))
    else:
        if not filtered:
            print("✅ No issues found.")
            sys.exit(0)
        # Group by severity for readable output
        by_sev = {}
        for issue in filtered:
            by_sev.setdefault(issue.severity, []).append(issue)
        for sev in ["ERROR", "WARN", "INFO"]:
            if sev not in by_sev:
                continue
            icon = {"ERROR": "🔴", "WARN": "🟡", "INFO": "🔵"}[sev]
            print(f"\n{icon} {sev} ({len(by_sev[sev])})")
            print("=" * 70)
            for issue in by_sev[sev]:
                print(f"  [{issue.shortcut}] {issue.location} → {issue.rule}")
                print(f"      {issue.detail}")

    error_count = sum(1 for i in all_issues if i.severity == "ERROR")
    warn_count = sum(1 for i in all_issues if i.severity == "WARN")
    print(f"\nSummary: {error_count} errors, {warn_count} warnings")

    sys.exit(2 if error_count > 0 else (1 if warn_count > 0 else 0))


if __name__ == "__main__":
    main()
