"""SkillGapReport and its nested structures (agents.md §2)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SkillGapPriority(StrEnum):
    """How urgently a gap should be addressed (agents.md §2)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SkillGap(BaseModel):
    """One missing or weak skill relative to the target role/postings.

    ``evidence`` and ``rationale`` are required (not optional) — every
    gap must be grounded in something specific about the candidate's
    profile, even if that something is its explicit absence (e.g. "no
    ML framework appears in skills or experience"). A gap with no
    evidence is exactly the generic, ungrounded advice agents.md §2 and
    rules.md AI Coding Rule 1 rule out; making the field required means
    an agent/LLM response missing it fails schema validation instead of
    silently shipping a hollow gap.
    """

    skill: str
    priority: SkillGapPriority
    rationale: str
    evidence: str


class SkillGapReport(BaseModel):
    """Output of the Skill Gap Agent (agents.md §2).

    Ephemeral/CLI-output only in v1 — not persisted to a repository
    (agents.md §2 Memory: "writes nothing persisted by default").
    """

    gaps: list[SkillGap] = Field(default_factory=list)
    summary: str | None = None
    insufficient_data: bool = False
