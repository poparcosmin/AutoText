"""Gmail fetcher — pull all email threads from a user inbox over a configurable
window range, save to corpus/raw/ as canonical JSON per thread, with
checkpointed monthly windows for resumability.

Standalone OAuth (google-auth-oauthlib). NU depinde de Claude Code, MCP,
sau alte tooling-uri externe. Reproductibil pe orice masina cu credentials.json.

Setup: vezi research/pipelines/ingest/README.md sectiunea "OAuth Setup"

Usage:
    # Stratified sample (1 sapt/luna):
    uv run --group research python research/pipelines/ingest/fetch_gmail.py \\
        --user contact@paff.ro --start 2024-04 --end 2026-04 --stratified

    # Full pull 24 luni:
    uv run --group research python research/pipelines/ingest/fetch_gmail.py \\
        --user contact@paff.ro --start 2024-04 --end 2026-04

    # Resume:
    ... --resume
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "research" / "pipelines" / "ingest"))

from parser import gmail_to_message  # noqa: E402
from schemas import IngestionState, Message, Thread, WindowState  # noqa: E402

# ============================================================
# Config
# ============================================================
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CORPUS_DIR = REPO_ROOT / "research" / "corpus" / "raw"
STATE_FILE = REPO_ROOT / "research" / "corpus" / "_state.json"
CREDENTIALS_FILE = REPO_ROOT / "research" / ".credentials" / "credentials.json"
TOKEN_FILE = REPO_ROOT / "research" / ".credentials" / "token.json"
AUDIT_LOG = REPO_ROOT / "research" / "audit.log"

THROTTLE_SLEEP_SECONDS = 0.1
PAGE_SIZE = 100

# ============================================================
# Logging + audit
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
log = structlog.get_logger("fetch_gmail")


def audit(action: str, **kwargs: object) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {"ts": datetime.now(timezone.utc).isoformat(), "action": action, **kwargs}
    )
    with AUDIT_LOG.open("a") as f:
        f.write(line + "\n")


# ============================================================
# OAuth
# ============================================================
def get_credentials() -> Credentials:
    creds: Credentials | None = None
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Missing OAuth credentials at {CREDENTIALS_FILE}.\n"
                    f"Setup: see research/pipelines/ingest/README.md"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        with TOKEN_FILE.open("w") as token:
            token.write(creds.to_json())
        log.info("oauth.token_saved", path=str(TOKEN_FILE))

    return creds


# ============================================================
# Gmail API wrappers — cu retry pe 429/500
# ============================================================
RETRYABLE = (HttpError,)


@retry(
    retry=retry_if_exception_type(RETRYABLE),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    reraise=True,
)
def list_messages(service, user_id: str, query: str, page_token: str | None) -> dict:
    return (
        service.users()
        .messages()
        .list(
            userId=user_id, q=query, pageToken=page_token, maxResults=PAGE_SIZE
        )
        .execute()
    )


@retry(
    retry=retry_if_exception_type(RETRYABLE),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    reraise=True,
)
def get_message(service, user_id: str, message_id: str) -> dict:
    return (
        service.users()
        .messages()
        .get(userId=user_id, id=message_id, format="full")
        .execute()
    )


# ============================================================
# Window planning
# ============================================================
def month_windows(start: str, end: str) -> list[str]:
    """['2024-04', '2024-05', ..., '2026-04']"""
    s = datetime.strptime(start + "-01", "%Y-%m-%d")
    e = datetime.strptime(end + "-01", "%Y-%m-%d")
    out = []
    cur = s
    while cur <= e:
        out.append(cur.strftime("%Y-%m"))
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return out


def window_to_query(window: str, stratified: bool = False) -> str:
    y, m = window.split("-")
    y_int, m_int = int(y), int(m)
    next_y, next_m = (y_int, m_int + 1) if m_int < 12 else (y_int + 1, 1)
    if stratified:
        next_first = datetime(next_y, next_m, 1)
        last_7_start = next_first - timedelta(days=7)
        return (
            f"after:{last_7_start.strftime('%Y/%m/%d')} "
            f"before:{next_first.strftime('%Y/%m/%d')}"
        )
    return f"after:{y}/{m}/01 before:{next_y:04d}/{next_m:02d}/01"


# ============================================================
# State persistence
# ============================================================
def load_state(user_email: str) -> IngestionState:
    if STATE_FILE.exists():
        with STATE_FILE.open() as f:
            return IngestionState.model_validate_json(f.read())
    now = datetime.now(timezone.utc)
    return IngestionState(user_email=user_email, started_at=now, updated_at=now)


def save_state(state: IngestionState) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state.updated_at = datetime.now(timezone.utc)
    with STATE_FILE.open("w") as f:
        f.write(state.model_dump_json(indent=2, by_alias=True))


# ============================================================
# Thread assembly + write
# ============================================================
def assemble_threads(messages: list[Message]) -> list[Thread]:
    by_thread: dict[str, list[Message]] = {}
    for m in messages:
        by_thread.setdefault(m.thread_id, []).append(m)

    threads: list[Thread] = []
    for tid, msgs in by_thread.items():
        msgs_sorted = sorted(msgs, key=lambda m: m.timestamp)
        threads.append(
            Thread(
                thread_id=tid,
                subject_root=msgs_sorted[0].headers.subject,
                message_ids=[m.message_id for m in msgs_sorted],
                messages=msgs_sorted,
                started_at=msgs_sorted[0].timestamp,
                last_message_at=msgs_sorted[-1].timestamp,
                turn_count=len(msgs_sorted),
            )
        )
    return threads


def write_thread(window: str, thread: Thread) -> Path:
    out_dir = CORPUS_DIR / window
    out_dir.mkdir(parents=True, exist_ok=True)
    short = thread.thread_id[:16]
    out = out_dir / f"thread-{short}.json"
    with out.open("w") as f:
        f.write(thread.model_dump_json(indent=2, by_alias=True))
    return out


# ============================================================
# Main fetch loop
# ============================================================
def fetch_window(
    service,
    user_email: str,
    window: str,
    state: IngestionState,
    stratified: bool = False,
    dry_run: bool = False,
) -> None:
    win_state = state.windows.get(window) or WindowState()
    if win_state.status == "done":
        log.info("window.skip", window=window, reason="already_done")
        return

    win_state.status = "fetching"
    win_state.last_attempt_at = datetime.now(timezone.utc)
    state.windows[window] = win_state
    save_state(state)

    query = window_to_query(window, stratified=stratified)
    log.info("window.start", window=window, query=query)
    audit("window_start", window=window, query=query, stratified=stratified)

    page_token = win_state.next_page_token
    message_ids: list[str] = []
    try:
        while True:
            resp = list_messages(service, "me", query, page_token)
            ids = [m["id"] for m in resp.get("messages", [])]
            message_ids.extend(ids)
            page_token = resp.get("nextPageToken")
            log.info("window.page", window=window, page_msgs=len(ids), running=len(message_ids))
            if not page_token:
                break
            time.sleep(THROTTLE_SLEEP_SECONDS)

        log.info("window.list_done", window=window, total=len(message_ids))
        if dry_run:
            win_state.status = "pending"
            win_state.message_count = len(message_ids)
            state.windows[window] = win_state
            save_state(state)
            return

        messages: list[Message] = []
        for i, mid in enumerate(message_ids):
            try:
                raw = get_message(service, "me", mid)
                messages.append(gmail_to_message(raw, user_email))
            except Exception as e:
                log.warning("message.fetch_error", message_id=mid, error=str(e))
                continue
            if (i + 1) % 50 == 0:
                log.info("window.progress", window=window, fetched=i + 1, total=len(message_ids))
            time.sleep(THROTTLE_SLEEP_SECONDS)

        threads = assemble_threads(messages)
        for t in threads:
            write_thread(window, t)

        win_state.status = "done"
        win_state.message_count = len(messages)
        win_state.thread_count = len(threads)
        win_state.completed_at = datetime.now(timezone.utc)
        win_state.error = None
        state.windows[window] = win_state
        state.total_messages += len(messages)
        state.total_threads += len(threads)
        save_state(state)

        log.info("window.done", window=window, messages=len(messages), threads=len(threads))
        audit("window_done", window=window, messages=len(messages), threads=len(threads))
    except Exception as e:
        win_state.status = "error"
        win_state.error = str(e)
        win_state.next_page_token = page_token
        state.windows[window] = win_state
        save_state(state)
        log.error("window.error", window=window, error=str(e))
        audit("window_error", window=window, error=str(e))
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Gmail to corpus/raw/")
    parser.add_argument("--user", required=True, help="Gmail account email")
    parser.add_argument("--start", required=True, help="Start window YYYY-MM")
    parser.add_argument("--end", required=True, help="End window YYYY-MM (inclusive)")
    parser.add_argument("--stratified", action="store_true", help="Doar ultimele 7 zile per luna")
    parser.add_argument("--resume", action="store_true", help="Skip windows marcate done")
    parser.add_argument("--dry-run", action="store_true", help="Doar count, nu fetch content")
    args = parser.parse_args()

    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    state = load_state(args.user)
    if state.user_email != args.user:
        log.warning("state.user_mismatch", existing=state.user_email, requested=args.user)
        state.user_email = args.user

    windows = month_windows(args.start, args.end)
    log.info("run.start", user=args.user, windows=windows, stratified=args.stratified)
    audit(
        "run_start",
        user=args.user,
        windows_count=len(windows),
        stratified=args.stratified,
        resume=args.resume,
        dry_run=args.dry_run,
    )

    for window in windows:
        if args.resume and (state.windows.get(window) and state.windows[window].status == "done"):
            log.info("run.skip_done", window=window)
            continue
        try:
            fetch_window(
                service,
                args.user,
                window,
                state,
                stratified=args.stratified,
                dry_run=args.dry_run,
            )
        except Exception as e:
            log.error("run.window_failed_continuing", window=window, error=str(e))
            continue

    log.info("run.done", total_messages=state.total_messages, total_threads=state.total_threads)
    audit("run_done", total_messages=state.total_messages, total_threads=state.total_threads)
    return 0


if __name__ == "__main__":
    sys.exit(main())
