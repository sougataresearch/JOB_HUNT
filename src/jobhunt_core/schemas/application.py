"""Application and ApplicationEvent schemas (database.md §9, §10)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class ApplicationStatus(StrEnum):
    """The application lifecycle (database.md §9)."""

    DRAFTED = "drafted"
    SUBMITTED = "submitted"
    SCREENING = "screening"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_COMPLETED = "interview_completed"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationEventSource(StrEnum):
    """Who/what recorded an ``ApplicationEvent`` (database.md §10)."""

    USER = "user"
    GMAIL_SYNC = "gmail_sync"
    SYSTEM = "system"


class Application(BaseModel):
    """A tracked application (agents.md §9, database.md §9).

    ``status`` is mutable current state; every transition is also
    recorded as an ``ApplicationEvent`` (design.md §3 -- soft state,
    hard history). ``resume_version_id``/``cover_letter_id`` were
    deferred until their owning tables existed (Phase 11/12); added
    here in Phase 14, now that both do. No field for an email
    reference -- database.md §9 defines no such column, and
    ``EmailDraft`` (agents.md §8) is never persisted independently.
    """

    id: str | None = None
    user_id: str | None = None
    job_posting_id: str
    resume_version_id: str | None = None
    cover_letter_id: str | None = None
    status: ApplicationStatus = ApplicationStatus.DRAFTED
    submitted_at: datetime | None = None
    source_channel: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ApplicationEvent(BaseModel):
    """One append-only status-transition record (database.md §10)."""

    id: str | None = None
    application_id: str
    from_status: ApplicationStatus | None = None
    to_status: ApplicationStatus
    note: str | None = None
    occurred_at: datetime | None = None
    source: ApplicationEventSource = ApplicationEventSource.USER
