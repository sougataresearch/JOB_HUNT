"""Document schemas: CV parsing (api.md §1), templates and resume renders (database.md §3, §14).

Phase 4's progress_log entry explicitly deferred ``templates`` and
``resume_versions`` to "Phase 11/12" -- built here, not scope creep.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ParsedDocument(BaseModel):
    """Raw text plus a best-effort section split from a parsed CV file."""

    raw_text: str
    sections: dict[str, str] = Field(default_factory=dict)
    source_format: Literal["pdf", "docx", "markdown"]


class Template(BaseModel):
    """A registered document template (database.md §14, decisions.md ADR-0008).

    ``file_path`` is relative to ``documents/templates/`` (the
    on-disk ``.tex.jinja`` source), matching how ``JobPosting.
    raw_content_path``/``CandidateProfile.source_file_path`` are also
    stored as paths, not file content, in the DB.
    """

    id: str | None = None
    kind: Literal["resume", "cover_letter"]
    name: str
    file_path: str
    description: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ResumeVersion(BaseModel):
    """A tailored, compiled CV render (database.md §3, agents.md §6 output).

    ``job_posting_id`` nullable = a generic/base version, not tied to
    one posting (database.md §3's own note) -- Phase 11 only ever
    creates posting-specific versions, but the field allows a future
    "base resume" generation path without a schema change.

    ``agent_run_id`` is a plain reference, not a DB foreign key --
    same deliberate deferral already applied to ``MatchScore``/
    ``ATSReport`` (Phases 8, 10): the ``agent_runs`` audit table
    itself remains unbuilt (progress_log.md, carried since Phase 4).
    """

    id: str | None = None
    profile_id: str
    job_posting_id: str | None = None
    template_id: str
    rendered_pdf_path: str
    rendered_tex_path: str
    ats_verification_passed: bool
    ats_extracted_text_path: str
    agent_run_id: str | None = None
    created_at: datetime | None = None


class PDFVerificationResult(BaseModel):
    """Outcome of the post-render pdftotext verification step (decisions.md ADR-0007).

    Not persisted as its own table -- folded into ``ResumeVersion.
    ats_verification_passed``/``ats_extracted_text_path``; this schema
    is the richer, in-memory result the render pipeline reasons about
    before collapsing it into those two fields.
    """

    passed: bool
    missing_headers: list[str] = Field(default_factory=list)
    extracted_text: str
    extracted_text_path: str


class TailoredExperienceEntry(BaseModel):
    """One reworded/trimmed experience entry within a ``ResumeDraft``."""

    title: str
    company: str
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] = Field(default_factory=list)


class ResumeDraft(BaseModel):
    """The drafter LLM call's output (agents.md §6, prompts.md §4).

    Deliberately narrower than a full resume: no name/email/phone/
    location/education -- those are pulled directly from
    ``CandidateProfile`` unchanged by the renderer, never touched by
    the LLM, which is one less surface for fabrication risk (the LLM
    only selects/rewords/trims what's already there, per rules.md AI
    Coding Rule 1).
    """

    summary: str
    skills: list[str] = Field(default_factory=list)
    experience: list[TailoredExperienceEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class ReviewVerdict(BaseModel):
    """The reviewer LLM call's output (agents.md §6 drafter->reviewer loop, prompts.md §4)."""

    approved: bool
    feedback: str
    fabrication_flags: list[str] = Field(default_factory=list)
