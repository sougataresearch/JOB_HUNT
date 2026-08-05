"""CandidateProfile and its nested structures (database.md §2)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ExperienceEntry(BaseModel):
    """One work-experience entry within a ``CandidateProfile``."""

    title: str
    company: str
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    """One education entry within a ``CandidateProfile``."""

    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class CandidateProfile(BaseModel):
    """The output of the Resume Analysis Agent (agents.md §1, database.md §2).

    ``id``/``created_at``/``updated_at`` are ``None`` before the first
    save and populated by the repository on persistence -- this one
    schema serves both the pre-save and post-load shape rather than
    splitting into separate Create/Read models (kept simple; revisit
    only if that split is ever actually needed).

    Fields left ``None``/empty mean "not found in the source CV" -- an
    agent producing this schema must never guess a value it isn't
    confident of (rules.md AI Coding Rule 1).
    """

    id: str | None = None
    user_id: str | None = None
    source_file_path: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    raw_extraction_confidence: dict[str, float] | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CandidateProfileExtraction(BaseModel):
    """What the Resume Analysis Agent's LLM call actually extracts.

    A narrower view of ``CandidateProfile`` excluding bookkeeping
    fields the model has no basis to fill in (``id``, ``user_id``,
    ``is_active``, ``created_at``, ``updated_at``,
    ``source_file_path``) -- those are set by the agent/repository,
    never requested from the LLM (agents.md §1).
    """

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    raw_extraction_confidence: dict[str, float] | None = None
