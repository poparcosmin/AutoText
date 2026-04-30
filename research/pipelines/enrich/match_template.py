"""Fuzzy match intre raspunsurile PAFF si cele 62 shortcut-uri din textsync_shortcut.

Scop: pentru fiecare mesaj outbound PAFF, identifica cu ce shortcut din DB se
potriveste (template_pure / template_modified / ad_hoc). Adauga aceasta info
in enriched JSON.

NU foloseste LLM — pure Python (rapidfuzz + chrf score).

Usage:
    uv run --group research python research/pipelines/enrich/match_template.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog

REPO_ROOT = Path(__file__).resolve().parents[3]

RAW_DIR = REPO_ROOT / "research" / "corpus" / "raw"
ENRICHED_DIR = REPO_ROOT / "research" / "corpus" / "enriched"
DB_PATH = REPO_ROOT / "db.sqlite3"
AUDIT_LOG = REPO_ROOT / "research" / "audit.log"

# Praguri matching (calibrate dupa primul run)
THRESHOLD_PURE = 0.85
THRESHOLD_MODIFIED = 0.60

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(colors=False),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
log = structlog.get_logger("match_template")


def audit(action: str, **kwargs: object) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {"ts": datetime.now(timezone.utc).isoformat(), "action": action, **kwargs}
    )
    with AUDIT_LOG.open("a") as f:
        f.write(line + "\n")


def load_shortcuts() -> list[dict]:
    """Citeste cele 62 shortcut-uri din SQLite."""
    if not DB_PATH.exists():
        log.error("db.not_found", path=str(DB_PATH))
        return []

    with sqlite3.connect(str(DB_PATH)) as con:
        con.row_factory = sqlite3.Row
        cur = con.execute(
            """
            SELECT s.id, s.key, s.value, s.content_type,
                   GROUP_CONCAT(ss.name) as set_names
            FROM textsync_shortcut s
            LEFT JOIN textsync_shortcut_sets l ON l.shortcut_id = s.id
            LEFT JOIN textsync_shortcutset ss ON ss.id = l.shortcutset_id
            GROUP BY s.id
            ORDER BY s.id
            """
        )
        return [
            {
                "id": row["id"],
                "key": row["key"],
                "value": row["value"],
                "content_type": row["content_type"],
                "sets": (row["set_names"] or "").split(",") if row["set_names"] else [],
                "char_count": len(row["value"] or ""),
            }
            for row in cur
        ]


def normalize_text(s: str) -> str:
    """Normalize pentru matching: lowercase, collapse whitespace, strip quoted replies."""
    if not s:
        return ""
    # Strip quoted replies (gmail format ">>>" or "> ")
    lines = []
    for line in s.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith(">"):
            continue
        lines.append(line)
    text = "\n".join(lines)
    # Collapse whitespace
    text = " ".join(text.split())
    return text.lower().strip()


def chrf_score(a: str, b: str, n: int = 6) -> float:
    """Character n-gram F-score (CHRF). Return float [0, 1].

    Standard reference: Popović, M. (2015). chrF: character n-gram F-score for
    automatic MT evaluation. https://aclanthology.org/W15-3049/
    """
    if not a or not b:
        return 0.0

    def ngrams(s: str, n: int) -> set[str]:
        return {s[i : i + n] for i in range(len(s) - n + 1)} if len(s) >= n else {s}

    a_ngrams = ngrams(a, n)
    b_ngrams = ngrams(b, n)
    if not a_ngrams or not b_ngrams:
        return 0.0
    common = a_ngrams & b_ngrams
    if not common:
        return 0.0
    precision = len(common) / len(b_ngrams)
    recall = len(common) / len(a_ngrams)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def best_match(paff_body: str, shortcuts: list[dict]) -> tuple[dict | None, float]:
    """Returneaza (best_shortcut_dict, score) sau (None, 0.0)."""
    paff_norm = normalize_text(paff_body)
    if not paff_norm or len(paff_norm) < 30:
        return None, 0.0

    best = None
    best_score = 0.0
    for sc in shortcuts:
        sc_norm = normalize_text(sc["value"])
        if len(sc_norm) < 20:
            continue
        score = chrf_score(paff_norm, sc_norm, n=4)
        if score > best_score:
            best_score = score
            best = sc
    return best, best_score


def classify_response_type(score: float) -> str:
    if score >= THRESHOLD_PURE:
        return "template_pure"
    if score >= THRESHOLD_MODIFIED:
        return "template_modified"
    return "ad_hoc"


def list_threads_for_processing() -> list[Path]:
    """Bootstrap-uieste enriched/ din raw/ daca lipseste, returneaza enriched paths.

    NU suprascrie enriched existent (pentru cazul cand classify_thread.py a rulat deja).
    """
    if not RAW_DIR.exists():
        return []
    out = []
    for raw in sorted(RAW_DIR.glob("*/thread-*.json")):
        rel = raw.relative_to(RAW_DIR)
        target = ENRICHED_DIR / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with raw.open() as fr:
                data = json.load(fr)
            data["_stage"] = "enriched"
            with target.open("w") as fe:
                json.dump(data, fe, ensure_ascii=False, indent=2)
        out.append(target)
    return out


def process_thread(path: Path, shortcuts: list[dict]) -> dict:
    """Adauga template_match pentru fiecare mesaj outbound. Returneaza stats."""
    with path.open() as f:
        thread = json.load(f)

    stats = {
        "messages_processed": 0,
        "matches_pure": 0,
        "matches_modified": 0,
        "ad_hoc": 0,
    }

    for msg in thread.get("messages", []):
        if msg.get("direction") != "outbound":
            continue
        body = msg.get("body", {}).get("text_plain", "")
        match, score = best_match(body, shortcuts)
        msg["template_match"] = {
            "shortcut_id": match["id"] if match else None,
            "shortcut_key": match["key"] if match else None,
            "similarity_chrf": round(score, 3),
            "response_type": classify_response_type(score),
        }
        stats["messages_processed"] += 1
        if msg["template_match"]["response_type"] == "template_pure":
            stats["matches_pure"] += 1
        elif msg["template_match"]["response_type"] == "template_modified":
            stats["matches_modified"] += 1
        else:
            stats["ad_hoc"] += 1

    thread["_template_matched_at"] = datetime.now(timezone.utc).isoformat()
    with path.open("w") as f:
        json.dump(thread, f, ensure_ascii=False, indent=2)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fuzzy match PAFF responses to shortcuts"
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--window", default=None, help="Filter pe window YYYY-MM")
    args = parser.parse_args()

    shortcuts = load_shortcuts()
    log.info("shortcuts.loaded", count=len(shortcuts))
    if not shortcuts:
        return 1

    threads = list_threads_for_processing()
    if args.window:
        threads = [t for t in threads if f"/{args.window}/" in str(t)]
    if args.limit:
        threads = threads[: args.limit]

    log.info("run.start", total_threads=len(threads))
    audit("template_match_start", total_threads=len(threads))

    aggregate = {
        "messages_processed": 0,
        "matches_pure": 0,
        "matches_modified": 0,
        "ad_hoc": 0,
    }
    for i, path in enumerate(threads):
        try:
            stats = process_thread(path, shortcuts)
            for k, v in stats.items():
                aggregate[k] += v
        except Exception as e:
            log.warning("thread.error", path=str(path), error=str(e))
        if (i + 1) % 100 == 0:
            log.info("run.progress", done=i + 1, total=len(threads), **aggregate)

    log.info("run.done", **aggregate)
    audit("template_match_done", **aggregate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
