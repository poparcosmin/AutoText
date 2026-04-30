"""Clasificare per thread via Gemini CLI (abonament, $0 cost).

Citeste thread-uri din corpus/raw/, ruleaza Gemini CLI cu prompt structurat,
salveaza enriched in corpus/enriched/. Idempotent — re-runs skip threads deja procesate.

Usage:
    # Dry run pe 5 thread-uri (validare prompt + output):
    uv run --group research python research/pipelines/enrich/classify_thread.py \\
        --limit 5 --verbose

    # Full run pe tot corpus/raw/:
    uv run --group research python research/pipelines/enrich/classify_thread.py

    # Resume:
    uv run --group research python research/pipelines/enrich/classify_thread.py --resume

    # Parallelism (default 1, max 10):
    uv run --group research python research/pipelines/enrich/classify_thread.py --workers 5
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import structlog

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "research" / "pipelines" / "ingest"))
sys.path.insert(0, str(REPO_ROOT / "research" / "pipelines" / "enrich"))

from prompts import CLASSIFIER_VERSION, render_thread_prompt  # noqa: E402

# ============================================================
# Config
# ============================================================
RAW_DIR = REPO_ROOT / "research" / "corpus" / "raw"
ENRICHED_DIR = REPO_ROOT / "research" / "corpus" / "enriched"
AUDIT_LOG = REPO_ROOT / "research" / "audit.log"

GEMINI_BIN = "gemini"
GEMINI_TIMEOUT_SECONDS = 120
GEMINI_MODEL = "gemini-3-pro"  # implicit din abonament; override with --model

# ============================================================
# Logging
# ============================================================
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(colors=False),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
log = structlog.get_logger("classify_thread")


def audit(action: str, **kwargs: object) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {"ts": datetime.now(timezone.utc).isoformat(), "action": action, **kwargs}
    )
    with AUDIT_LOG.open("a") as f:
        f.write(line + "\n")


# ============================================================
# Gemini CLI wrapper
# ============================================================
def call_gemini(prompt: str, model: str = GEMINI_MODEL) -> str:
    """Run gemini CLI non-interactive, return raw stdout text."""
    cmd = [GEMINI_BIN, "-p", prompt]
    if model:
        cmd.extend(["-m", model])
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=GEMINI_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Gemini CLI timeout after {GEMINI_TIMEOUT_SECONDS}s")

    if result.returncode != 0:
        raise RuntimeError(
            f"Gemini CLI failed (rc={result.returncode}): {result.stderr[:500]}"
        )
    return result.stdout


def extract_json_from_response(text: str) -> dict:
    """Parse JSON din output Gemini CLI. Tolereaza markdown code fences si preamble."""
    # Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Try extract from ```json ... ```
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try first { ... last } (greedy)
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not extract valid JSON from response (first 500 chars): {text[:500]}"
    )


# ============================================================
# Thread processing
# ============================================================
def list_raw_threads() -> list[Path]:
    """Returneaza toate fisierele thread-*.json din corpus/raw/, sortate."""
    if not RAW_DIR.exists():
        return []
    return sorted(RAW_DIR.glob("*/thread-*.json"))


def enriched_path(raw_path: Path) -> Path:
    """raw/2024-04/thread-abc.json → enriched/2024-04/thread-abc.json"""
    rel = raw_path.relative_to(RAW_DIR)
    return ENRICHED_DIR / rel


def is_already_enriched(raw_path: Path) -> bool:
    target = enriched_path(raw_path)
    return target.exists() and target.stat().st_size > 0


def classify_one_thread(
    raw_path: Path, model: str, verbose: bool = False
) -> tuple[Path, dict]:
    """Process un singur thread JSON. Returneaza (path, classification dict)."""
    with raw_path.open() as f:
        thread_data = json.load(f)

    # Trim mesaje pentru prompt (max 50KB body per mesaj — protectie tokens)
    for msg in thread_data.get("messages", []):
        body = msg.get("body", {})
        text = body.get("text_plain", "")
        if len(text) > 5000:
            body["text_plain"] = text[:5000] + "\n\n[...TRUNCATED...]"
            body["char_count"] = 5000

    thread_json = json.dumps(thread_data, ensure_ascii=False)
    prompt = render_thread_prompt(thread_json)

    if verbose:
        log.info(
            "thread.start",
            thread_id=thread_data.get("thread_id"),
            prompt_len=len(prompt),
        )

    response = call_gemini(prompt, model=model)

    if verbose:
        log.info("thread.response_received", response_len=len(response))

    classification = extract_json_from_response(response)
    classification["_classified_at"] = datetime.now(timezone.utc).isoformat()
    classification["_classifier_version"] = CLASSIFIER_VERSION
    classification["_raw_thread_path"] = str(raw_path.relative_to(REPO_ROOT))

    return raw_path, classification


def write_enriched(raw_path: Path, classification: dict) -> Path:
    """Combina raw thread + classification, scrie in corpus/enriched/."""
    with raw_path.open() as f:
        raw_data = json.load(f)

    enriched = {
        "_schema_version": "1.0",
        "_stage": "enriched",
        **raw_data,
        "classification": classification,
    }

    out = enriched_path(raw_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
    return out


# ============================================================
# Main loop
# ============================================================
def process_thread_safe(args_tuple: tuple) -> dict:
    raw_path, model, verbose = args_tuple
    try:
        _, classification = classify_one_thread(raw_path, model, verbose=verbose)
        out = write_enriched(raw_path, classification)
        return {"status": "ok", "raw_path": str(raw_path), "enriched_path": str(out)}
    except Exception as e:
        log.warning("thread.error", path=str(raw_path), error=str(e))
        return {"status": "error", "raw_path": str(raw_path), "error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify threads via Gemini CLI")
    parser.add_argument(
        "--limit", type=int, default=None, help="Max threads to process (debug)"
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="Parallel workers (1-10)"
    )
    parser.add_argument(
        "--resume", action="store_true", help="Skip threads already in enriched/"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Verbose per-thread logging"
    )
    parser.add_argument("--model", default=GEMINI_MODEL, help="Gemini model")
    parser.add_argument(
        "--window",
        default=None,
        help="Process only threads from a specific window (YYYY-MM)",
    )
    args = parser.parse_args()

    if args.workers < 1 or args.workers > 10:
        log.error("invalid.workers", value=args.workers)
        return 1

    threads = list_raw_threads()
    if args.window:
        threads = [t for t in threads if f"/{args.window}/" in str(t)]
    if args.resume:
        threads = [t for t in threads if not is_already_enriched(t)]
    if args.limit:
        threads = threads[: args.limit]

    log.info(
        "run.start", total_threads=len(threads), workers=args.workers, model=args.model
    )
    audit(
        "classify_run_start",
        total_threads=len(threads),
        workers=args.workers,
        model=args.model,
    )

    if not threads:
        log.info("run.nothing_to_do")
        return 0

    start_ts = time.time()
    ok_count = 0
    err_count = 0

    if args.workers == 1:
        for i, raw_path in enumerate(threads):
            result = process_thread_safe((raw_path, args.model, args.verbose))
            if result["status"] == "ok":
                ok_count += 1
            else:
                err_count += 1
            if (i + 1) % 25 == 0 or args.verbose:
                elapsed = time.time() - start_ts
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta_s = (len(threads) - i - 1) / rate if rate > 0 else 0
                log.info(
                    "run.progress",
                    done=i + 1,
                    total=len(threads),
                    ok=ok_count,
                    err=err_count,
                    rate_per_sec=round(rate, 2),
                    eta_minutes=round(eta_s / 60, 1),
                )
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {
                ex.submit(process_thread_safe, (t, args.model, args.verbose)): t
                for t in threads
            }
            for i, fut in enumerate(as_completed(futures)):
                result = fut.result()
                if result["status"] == "ok":
                    ok_count += 1
                else:
                    err_count += 1
                if (i + 1) % 25 == 0:
                    elapsed = time.time() - start_ts
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    eta_s = (len(threads) - i - 1) / rate if rate > 0 else 0
                    log.info(
                        "run.progress",
                        done=i + 1,
                        total=len(threads),
                        ok=ok_count,
                        err=err_count,
                        rate_per_sec=round(rate, 2),
                        eta_minutes=round(eta_s / 60, 1),
                    )

    elapsed = time.time() - start_ts
    log.info(
        "run.done",
        ok=ok_count,
        err=err_count,
        total=len(threads),
        duration_seconds=round(elapsed, 1),
    )
    audit(
        "classify_run_done",
        ok=ok_count,
        err=err_count,
        total=len(threads),
        duration_seconds=round(elapsed, 1),
    )
    return 0 if err_count == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
