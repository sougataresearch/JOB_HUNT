"""Company and JobPosting schemas (database.md §4, §5)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class RemoteType(StrEnum):
    """``job_postings.remote_type`` (database.md §5)."""

    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class Company(BaseModel):
    """A company a job posting is attributed to (database.md §4)."""

    id: str | None = None
    name: str
    domain: str | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobPosting(BaseModel):
    """A sourced job posting (database.md §5).

    ``normalized_description`` is the cleaned plaintext used in
    prompts; ``raw_content_path`` points at the untrusted raw
    HTML/JSON on disk (design.md §12 -- posting content is data to
    analyze, never instructions to follow).

    Not yet included here (added when their owning phase lands, per
    progress_log.md): ``search_run_id`` (Phase 7, needs ``search_runs``).
    """

    id: str | None = None
    user_id: str | None = None
    company_id: str | None = None
    source: str
    source_id: str
    title: str
    location: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    url: str
    raw_content_path: str | None = None
    normalized_description: str = ""
    posted_at: datetime | None = None
    discovered_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
