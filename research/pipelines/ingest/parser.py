"""Gmail message → canonical schema parser.

Pure functions — no I/O, no API calls. Test-friendly.
"""
from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime

from schemas import Attachment, Body, EmailAddress, Headers, Message


def parse_address(raw: str) -> EmailAddress:
    name, email = parseaddr(raw or "")
    return EmailAddress(name=name or None, email=email)


def parse_address_list(raw: str | None) -> list[EmailAddress]:
    if not raw:
        return []
    return [parse_address(part.strip()) for part in raw.split(",") if part.strip()]


def header_value(headers: list[dict], name: str) -> str | None:
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value")
    return None


def _decode_b64(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_body_text(payload: dict) -> str:
    """Walk payload tree, extract text/plain. Fallback to text/html stripped."""

    def _walk(part: dict) -> tuple[str, str]:
        plain = ""
        html = ""
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")

        if mime == "text/plain" and data:
            plain = _decode_b64(data)
        elif mime == "text/html" and data:
            html = _decode_b64(data)

        for sub in part.get("parts") or []:
            sub_plain, sub_html = _walk(sub)
            plain = plain or sub_plain
            html = html or sub_html

        return plain, html

    plain, html = _walk(payload)
    if plain:
        return plain
    if html:
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    return ""


def extract_attachments(payload: dict) -> list[Attachment]:
    out: list[Attachment] = []

    def _walk(part: dict) -> None:
        filename = part.get("filename")
        body = part.get("body", {})
        if filename and body.get("attachmentId"):
            out.append(
                Attachment(
                    filename=filename,
                    mime_type=part.get("mimeType", ""),
                    size_bytes=int(body.get("size", 0)),
                    attachment_id=body.get("attachmentId"),
                )
            )
        for sub in part.get("parts") or []:
            _walk(sub)

    _walk(payload)
    return out


def detect_direction(from_email: str, to_emails: list[str], user_email: str) -> str:
    user = user_email.lower()
    if from_email.lower() == user:
        return "outbound"
    if user in {e.lower() for e in to_emails}:
        return "inbound"
    return "unknown"


def gmail_to_message(raw: dict, user_email: str) -> Message:
    """Convert un raw Gmail API response in canonical Message."""
    headers_list = raw.get("payload", {}).get("headers", [])

    from_addr = parse_address(header_value(headers_list, "From") or "")
    to_addrs = parse_address_list(header_value(headers_list, "To"))
    cc_addrs = parse_address_list(header_value(headers_list, "Cc"))
    subject = header_value(headers_list, "Subject") or ""

    date_raw = header_value(headers_list, "Date")
    try:
        if date_raw:
            timestamp = parsedate_to_datetime(date_raw)
            # parsedate_to_datetime returneaza naive cand TZ lipseste din header.
            # Forteaza timezone-aware (UTC) pentru a evita conflict la sort.
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = datetime.fromtimestamp(
                int(raw["internalDate"]) / 1000, tz=timezone.utc
            )
    except (TypeError, ValueError):
        timestamp = datetime.fromtimestamp(
            int(raw.get("internalDate", 0)) / 1000, tz=timezone.utc
        )

    in_reply_to = header_value(headers_list, "In-Reply-To")
    references_raw = header_value(headers_list, "References") or ""
    references = [r.strip() for r in references_raw.split() if r.strip()]
    rfc_msg_id = header_value(headers_list, "Message-ID")

    body_text = extract_body_text(raw.get("payload", {}))
    body = Body(
        text_plain=body_text,
        char_count=len(body_text),
        word_count=len(body_text.split()),
    )

    direction = detect_direction(
        from_addr.email, [a.email for a in to_addrs], user_email
    )

    headers = Headers(
        from_=from_addr,
        to=to_addrs,
        cc=cc_addrs,
        subject=subject,
        in_reply_to=in_reply_to,
        references=references,
        message_id_rfc=rfc_msg_id,
    )

    return Message(
        message_id=raw["id"],
        thread_id=raw["threadId"],
        timestamp=timestamp,
        direction=direction,  # type: ignore[arg-type]
        headers=headers,
        body=body,
        attachments=extract_attachments(raw.get("payload", {})),
        labels=raw.get("labelIds", []),
        fetched_at=datetime.now(timezone.utc),
    )
