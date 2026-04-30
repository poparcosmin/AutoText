"""Pydantic schemas for raw Gmail message + thread + ingestion state.

Canonic format pentru tot pipeline-ul de research. Orice script care
citeste/scrie date din corpus/raw/ TREBUIE sa importe de aici.

Versiune schema: 1.0
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION: Literal["1.0"] = "1.0"


class EmailAddress(BaseModel):
    name: str | None = None
    email: str


class Attachment(BaseModel):
    filename: str
    mime_type: str
    size_bytes: int
    attachment_id: str | None = None


class Headers(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: EmailAddress = Field(alias="from")
    to: list[EmailAddress] = Field(default_factory=list)
    cc: list[EmailAddress] = Field(default_factory=list)
    bcc: list[EmailAddress] = Field(default_factory=list)
    subject: str = ""
    reply_to: str | None = None
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    message_id_rfc: str | None = None


class Body(BaseModel):
    text_plain: str = ""
    char_count: int = 0
    word_count: int = 0


class Message(BaseModel):
    """Un singur mesaj Gmail (un email individual)."""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: Literal["1.0"] = Field(
        default=SCHEMA_VERSION, alias="_schema_version"
    )
    stage: Literal["raw", "enriched"] = Field(default="raw", alias="_stage")

    message_id: str
    thread_id: str
    timestamp: datetime
    direction: Literal["inbound", "outbound", "system_notification", "unknown"]
    headers: Headers
    body: Body
    attachments: list[Attachment] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)

    fetched_at: datetime
    fetcher_version: str = "fetch_gmail.py-v1.0"


class Thread(BaseModel):
    """Group complete de mesaje cu acelasi thread_id."""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: Literal["1.0"] = Field(
        default=SCHEMA_VERSION, alias="_schema_version"
    )
    thread_id: str
    subject_root: str
    message_ids: list[str] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    started_at: datetime
    last_message_at: datetime
    turn_count: int = 0


class WindowState(BaseModel):
    """State pentru un singur window lunar in fetch loop."""

    status: Literal["pending", "fetching", "done", "error"] = "pending"
    message_count: int = 0
    thread_count: int = 0
    next_page_token: str | None = None
    last_attempt_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class IngestionState(BaseModel):
    """Persistent state pentru fetch_gmail.py — checkpointing."""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: Literal["1.0"] = Field(
        default=SCHEMA_VERSION, alias="_schema_version"
    )
    user_email: str
    started_at: datetime
    updated_at: datetime
    windows: dict[str, WindowState] = Field(default_factory=dict)
    total_messages: int = 0
    total_threads: int = 0


__all__ = [
    "SCHEMA_VERSION",
    "EmailAddress",
    "Attachment",
    "Headers",
    "Body",
    "Message",
    "Thread",
    "WindowState",
    "IngestionState",
]
