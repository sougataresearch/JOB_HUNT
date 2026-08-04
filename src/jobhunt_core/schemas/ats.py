"""ATSReport schema (database.md §7)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ATSReport(BaseModel):
    """ATS Optimization Agent output (agents.md §5, database.md §7).

    ``supported_gaps`` are keywords missing but backed by real
    candidate experience (safe to add, reworded); ``unsupported_gaps``
    are missing *and* unbacked -- must never be fabricated into a
    generated document (rules.md AI Coding Rule 1).
    """

    id: str | None = None
    job_posting_id: str
    profile_id: str
    supported_gaps: list[str] = Field(default_factory=list)
    unsupported_gaps: list[str] = Field(default_factory=list)
    formatting_warnings: list[str] = Field(default_factory=list)
    agent_run_id: str | None = None
    created_at: datetime | None = None
