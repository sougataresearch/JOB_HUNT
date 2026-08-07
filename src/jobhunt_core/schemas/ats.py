"""ATSReport schema and the ATS Optimization Agent's LLM-output schema.

database.md §7, agents.md §5.
"""

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


class ATSGapClassification(BaseModel):
    """What the ATS Optimization Agent's LLM judgment step actually produces (agents.md §5).

    Narrower than ``ATSReport``, same ``CandidateProfileExtraction``/
    ``MatchScoreExtraction`` pattern (Phases 5, 8): excludes fields the
    model has no basis to fill in (``id``, ``job_posting_id``,
    ``profile_id``, ``agent_run_id``, ``created_at``, and
    ``formatting_warnings`` -- a document-formatting concern outside
    what a structured ``CandidateProfile`` + posting-text comparison
    can determine, always empty from this agent; see
    ``ats_optimization_agent.py``). The model only classifies gaps
    the deterministic keyword-extraction step already found -- it
    never invents a gap of its own.
    """

    supported_gaps: list[str] = Field(default_factory=list)
    unsupported_gaps: list[str] = Field(default_factory=list)
