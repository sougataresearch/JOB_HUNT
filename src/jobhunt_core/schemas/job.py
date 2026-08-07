"""Company, JobPosting, and Job Search API schemas (database.md §4, §5, §17; api.md §2)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


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
    search_run_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SearchQuery(BaseModel):
    """A Job Search Agent run's parameters (api.md §2)."""

    keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote_ok: bool = True
    posted_within_days: int | None = None


class RawPosting(BaseModel):
    """One posting as a ``JobSource`` returns it, before normalization (api.md §2).

    ``raw_content`` is untrusted input (design.md §12) -- a prompt that
    interpolates it must wrap it in an explicit delimiter block, never
    treat it as instructions.
    """

    source: str
    source_id: str
    title: str
    company: str
    location: str
    url: str
    raw_content: str
    fetched_at: datetime


class SearchRun(BaseModel):
    """One Job Search Agent run's audit record (database.md §17)."""

    id: str | None = None
    user_id: str | None = None
    query: SearchQuery
    sources_queried: list[str] = Field(default_factory=list)
    postings_found: int = 0
    postings_deduped_new: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
