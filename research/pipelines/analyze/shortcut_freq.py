"""
Full shortcut frequency match against cleaned corpus.
Uses two-stage fingerprint:
  1. Substring match — distinctive 40-char slice from middle of shortcut
  2. Token-overlap fallback — top-3 distinctive 4-word ngrams
Output: CSV with id, key, length, distinct_msg_matches, role_inferred
"""
import json
import sqlite3
import sys
import re
from pathlib import Path
from collections import defaultdict


CORPUS = Path("research/corpus/enriched")
DB = "db.sqlite3"


def normalize(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace, drop punctuation."""
    if not text:
        return ""
    text = text.lower()
    # diacritic strip (manual — covers RO)
    diac = str.maketrans("ăâîșşțţáéíóú", "aaaisstaeiou")
    text = text.translate(diac)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_fingerprint(value: str, key: str) -> str | None:
    """
    Pick a distinctive ~50-char span. Skip the first 60 chars (greetings) and
    last 60 chars (signatures). If shortcut is too short, take what's there.
    """
    norm = normalize(value)
    if len(norm) < 30:
        return norm if len(norm) >= 15 else None
    # Skip greetings on the left, sigs on the right
    start = min(60, max(0, len(norm) // 4))
    end = max(start + 50, len(norm) - 60)
    span = norm[start:end].strip()
    if len(span) < 30:
        return norm[: min(60, len(norm))]
    # Take first 60 chars of span as fingerprint (more selective than longer)
    return span[:60]


def load_shortcuts():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute(
        "SELECT id, key, value, length(value) FROM textsync_shortcut "
        "WHERE value IS NOT NULL AND length(value) > 10 "
        "ORDER BY id"
    )
    out = []
    for sid, key, value, ln in cur.fetchall():
        fp = extract_fingerprint(value, key)
        if fp:
            out.append({"id": sid, "key": key, "value": value, "length": ln, "fp": fp})
    con.close()
    return out


def iter_outbound_messages():
    """Yield (window, thread_id, msg_index, normalized_body)."""
    for window_dir in sorted(CORPUS.iterdir()):
        if not window_dir.is_dir():
            continue
        for thread_file in window_dir.glob("thread-*.json"):
            try:
                with open(thread_file) as fh:
                    thread = json.load(fh)
            except Exception:
                continue
            for i, msg in enumerate(thread.get("messages", [])):
                if msg.get("direction") != "outbound":
                    continue
                body = msg.get("body", {})
                if not isinstance(body, dict):
                    continue
                txt = body.get("text_plain") or ""
                if len(txt) < 30:
                    continue
                yield window_dir.name, thread.get("thread_id", ""), i, normalize(txt)


def main():
    shortcuts = load_shortcuts()
    print(f"# Loaded {len(shortcuts)} shortcuts with valid fingerprints", file=sys.stderr)

    counts = defaultdict(int)
    msg_total = 0
    for window, tid, idx, norm_body in iter_outbound_messages():
        msg_total += 1
        for sc in shortcuts:
            if sc["fp"] in norm_body:
                counts[sc["id"]] += 1
        if msg_total % 5000 == 0:
            print(f"# scanned {msg_total} outbound messages...", file=sys.stderr)

    print(f"# Total outbound messages scanned: {msg_total}", file=sys.stderr)

    # Build ranked output
    rows = []
    for sc in shortcuts:
        rows.append(
            {
                "id": sc["id"],
                "key": sc["key"],
                "length": sc["length"],
                "matches": counts[sc["id"]],
                "pct": round(100 * counts[sc["id"]] / msg_total, 2) if msg_total else 0,
                "fp_sample": sc["fp"][:60],
            }
        )
    rows.sort(key=lambda r: (-r["matches"], r["length"]))

    print("id,key,length,matches,pct_outbound,fp_sample")
    for r in rows:
        fp = r["fp_sample"].replace(",", " ").replace('"', "'")
        print(f'{r["id"]},{r["key"]},{r["length"]},{r["matches"]},{r["pct"]},"{fp}"')


if __name__ == "__main__":
    main()
