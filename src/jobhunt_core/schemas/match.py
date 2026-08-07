"""MatchScore and Ranking API schemas (database.md §6, api.md §3)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MatchScore(BaseModel):
    """Job Matching Agent output (agents.md §4, database.md §6).

    ``rationale`` is never omitted -- a bare score is not acceptable
    output (design.md §2). ``agent_run_id`` is a plain reference (no DB
    foreign key yet -- the ``agent_runs`` audit table is added once an
    agent actually runs, Phase 5+).
    """

    id: str | None = None
    job_posting_id: str
    profile_id: str
    score: float
    matched_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    rationale: str
    agent_run_id: str | None = None
    created_at: datetime | None = None


class MatchScoreExtraction(BaseModel):
    """What the Job Matching Agent's LLM call actually produces (agents.md §4).

    Narrower than ``MatchScore``, excluding fields the model has no
    basis to fill in (``id``, ``job_posting_id``, ``profile_id``,
    ``agent_run_id``, ``created_at``) -- those are set by the agent,
    same pattern as ``CandidateProfileExtraction`` (Phase 5).
    """

    score: float
    matched_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    rationale: str


class RankedPosting(BaseModel):
    """One entry in a ranked shortlist (api.md §3 Ranking API, Phase 9).

    ``job_id`` names api.md §3's field as-documented (``MatchScore``
    itself already carries the same value as ``job_posting_id``).
    """

    job_id: str
    score: MatchScore
    rank: int
