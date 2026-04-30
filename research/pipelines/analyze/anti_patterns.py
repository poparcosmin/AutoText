"""Anti-pattern scanner — caut la scale cele 8+ anti-pattern-uri din Brand-Voice.

NU foloseste LLM — pure regex + heuristics. Scaleaza pe orice volum.

Output:
- corpus/enriched/_anti_patterns_summary.json — agregare statistica
- adauga `anti_patterns_regex` la fiecare mesaj outbound in enriched JSON

Usage:
    uv run --group research python research/pipelines/analyze/anti_patterns.py
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import structlog

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "research" / "corpus" / "raw"
ENRICHED_DIR = REPO_ROOT / "research" / "corpus" / "enriched"
SPAM_DIR = REPO_ROOT / "research" / "corpus" / "spam"
SUMMARY_PATH = ENRICHED_DIR / "_anti_patterns_summary.json"
AUDIT_LOG = REPO_ROOT / "research" / "audit.log"

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(colors=False),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
log = structlog.get_logger("anti_patterns")


def audit(action: str, **kwargs: object) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {"ts": datetime.now(timezone.utc).isoformat(), "action": action, **kwargs}
    )
    with AUDIT_LOG.open("a") as f:
        f.write(line + "\n")


# ============================================================
# Detection rules
# ============================================================
DIACRITICS_RO = "ăâîșțĂÂÎȘȚ"


def has_diacritics(text: str) -> bool:
    return any(c in DIACRITICS_RO for c in text)


def first_n_words(text: str, n: int = 30) -> str:
    return " ".join(text.split()[:n])


def strip_quoted(text: str) -> str:
    """Elimina quoted replies (>>>, gmail format)."""
    lines = []
    for line in text.split("\n"):
        if line.lstrip().startswith(">"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def detect_anti_patterns(body: str) -> list[str]:
    """Returneaza lista cu codurile anti-pattern detectate in body-ul PAFF."""
    detected: list[str] = []
    body_clean = strip_quoted(body)
    if not body_clean:
        return detected

    body_lower = body_clean.lower()
    first_30w = first_n_words(body_clean, 30)
    first_30w_lower = first_30w.lower()

    # 1. salut_fara_diacritice — "Buna" in loc de "Bună"
    if re.search(r"\bbuna\s+(ziua|dimineața|seara|dimineata)\b", first_30w_lower):
        detected.append("salut_fara_diacritice")

    # 2. salut_fara_virgula — "Bună ziua" fara virgula la final
    salut_match = re.search(
        r"\b(bună|buna)\s+(ziua|dimineața|seara|dimineata)([^,\n]|$)",
        first_30w_lower,
    )
    if salut_match and "," not in salut_match.group(0):
        detected.append("salut_fara_virgula")

    # 3. salut_cu_spatiu_punct — "Buna ziua ." cu spatiu+punct
    if re.search(r"\b(bună|buna)\s+(ziua|dimineața|seara)\s+\.", first_30w_lower):
        detected.append("salut_cu_spatiu_punct")

    # 4. eta_47_zile_template
    if re.search(r"\b4[\s-]+7\s+zile\s+lucr", body_lower):
        detected.append("eta_47_zile_template")

    # 5. brand_signature_drift — detector REVIZUIT 2026-04-29
    # Cauza reala identificata: variatii in signature Gmail (37 variante distincte
    # pe corpus de 25 luni). Forma "Producător de Ambalaje" (cu "de") e fictiva —
    # 0/66052 mesaje. Forma reala dominantă e "Producător ambalaje" (24k ocurențe).
    #
    # Anti-pattern util de detectat = signature WITHOUT diacritică pe "Producător":
    # - "Producator ambalaje" (lipseste diacritica)
    # - "Producator de ambalaje"
    # - "Fabrica de ambalaje" (descriptor diferit, semnal de signature legacy)
    # NU mai detectam "Producător Ambalaje" cu A mare ca wrong — e variantă normală.
    has_paff_brand = bool(re.search(r"PAFF\s*[:·\-]+", body_clean, re.IGNORECASE))
    if has_paff_brand:
        if (
            re.search(r"Fabric[a]\s+(de\s+)?[Aa]mbalaje", body_clean)
            or re.search(r"Producator\s+[Aa]mbalaje", body_clean)
            or re.search(r"Producator\s+de\s+[Aa]mbalaje", body_clean)
        ):
            detected.append("brand_signature_drift")

    # 6. mode_telegrafic — <30 cuvinte fara salut + fara semnatura
    word_count = len(body_clean.split())
    has_salut = bool(re.search(r"\b(bună|buna)\s+(ziua|dimineața|seara)", body_lower))
    has_sign = bool(
        re.search(
            r"\bcu\s+stim[ăa]\b|\bsalut[ăa]ri\b|\baura\b|\bflorentina\b", body_lower
        )
    )
    if word_count < 30 and not has_salut and not has_sign:
        detected.append("mode_telegrafic")

    # 7. lipsa_diacritice_partial — body are <40% caractere posibil-diacritice cu diacritica
    # Heuristic: cuvinte care AR TREBUI sa aiba diacritice apar fara
    expected_with_diacritics = [
        ("multumim", "mulțumim"),
        ("multumesc", "mulțumesc"),
        ("pregatim", "pregătim"),
        ("astept", "aștept"),
        ("comanda ", "comandă "),
        ("livrarea", "livrarea"),
        ("plata", "plată"),
        ("imediat", "imediat"),
        ("masura", "măsură"),
        ("dragut", "drăguț"),
        ("fata", "față"),
        ("recomanda", "recomandă"),
        ("trebuie", "trebuie"),
    ]
    issues = sum(1 for missing, _ in expected_with_diacritics if missing in body_lower)
    if issues >= 2:
        detected.append("lipsa_diacritice_partial")

    return detected


# ============================================================
# Main
# ============================================================
def list_threads_for_processing() -> list[Path]:
    """Bootstrap enriched/ din raw/ daca lipseste, returneaza enriched paths.

    Skip threads care sunt in corpus/spam/ (mutate de quarantine_spam.py).
    """
    if not RAW_DIR.exists():
        return []
    # Build set of quarantined relative paths
    quarantined: set[str] = set()
    if SPAM_DIR.exists():
        for sp in SPAM_DIR.glob("*/thread-*.json"):
            rel = sp.relative_to(SPAM_DIR).as_posix()
            quarantined.add(rel)

    out = []
    for raw in sorted(RAW_DIR.glob("*/thread-*.json")):
        rel_path = raw.relative_to(RAW_DIR)
        if rel_path.as_posix() in quarantined:
            continue
        target = ENRICHED_DIR / rel_path
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with raw.open() as fr:
                data = json.load(fr)
            data["_stage"] = "enriched"
            with target.open("w") as fe:
                json.dump(data, fe, ensure_ascii=False, indent=2)
        out.append(target)
    return out


def process_thread(path: Path) -> dict:
    """Returneaza stats per thread + scrie anti_patterns_regex in mesaje."""
    with path.open() as f:
        thread = json.load(f)

    pattern_counts: Counter = Counter()
    msgs_scanned = 0

    for msg in thread.get("messages", []):
        if msg.get("direction") != "outbound":
            continue
        body = msg.get("body", {}).get("text_plain", "")
        detected = detect_anti_patterns(body)
        msg["anti_patterns_regex"] = detected
        for ap in detected:
            pattern_counts[ap] += 1
        msgs_scanned += 1

    thread["_anti_patterns_scanned_at"] = datetime.now(timezone.utc).isoformat()
    with path.open("w") as f:
        json.dump(thread, f, ensure_ascii=False, indent=2)

    return {
        "msgs_scanned": msgs_scanned,
        "by_pattern": dict(pattern_counts),
        "thread_id": thread.get("thread_id"),
        "window": path.parent.name,
    }


def aggregate(per_thread: list[dict]) -> dict:
    by_pattern: Counter = Counter()
    by_window_pattern: dict[str, Counter] = defaultdict(Counter)
    total_msgs = 0
    threads_with_any = 0

    for stats in per_thread:
        total_msgs += stats["msgs_scanned"]
        if stats["by_pattern"]:
            threads_with_any += 1
        for ap, c in stats["by_pattern"].items():
            by_pattern[ap] += c
            by_window_pattern[stats["window"]][ap] += c

    return {
        "total_messages_scanned": total_msgs,
        "total_threads_scanned": len(per_thread),
        "threads_with_at_least_one_anti_pattern": threads_with_any,
        "patterns_total_count": dict(by_pattern.most_common()),
        "patterns_per_message_rate": {
            ap: round(c / total_msgs, 4) if total_msgs else 0
            for ap, c in by_pattern.items()
        },
        "by_window": {
            w: dict(cnt.most_common()) for w, cnt in by_window_pattern.items()
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Anti-pattern scanner")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--window", default=None)
    args = parser.parse_args()

    threads = list_threads_for_processing()
    if args.window:
        threads = [t for t in threads if f"/{args.window}/" in str(t)]
    if args.limit:
        threads = threads[: args.limit]

    log.info("run.start", total_threads=len(threads))
    audit("anti_patterns_start", total_threads=len(threads))

    per_thread = []
    for i, path in enumerate(threads):
        try:
            per_thread.append(process_thread(path))
        except Exception as e:
            log.warning("thread.error", path=str(path), error=str(e))
        if (i + 1) % 200 == 0:
            log.info("run.progress", done=i + 1, total=len(threads))

    summary = aggregate(per_thread)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_PATH.open("w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log.info("run.done", **{k: v for k, v in summary.items() if k != "by_window"})
    audit(
        "anti_patterns_done", **{k: v for k, v in summary.items() if k != "by_window"}
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
