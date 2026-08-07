"""Template, ResumeVersion, and CoverLetter SQLAlchemy models (database.md §3, §8, §14)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from jobhunt_core.storage.models.base import Base, TimestampMixin, UUIDPKMixin, utcnow


class TemplateModel(UUIDPKMixin, TimestampMixin, Base):
    """The ``templates`` table -- unique per ``(kind, name)`` (database.md §14)."""

    __tablename__ = "templates"
    __table_args__ = (UniqueConstraint("kind", "name", name="uq_templates_kind_name"),)

    kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")


class ResumeVersionModel(UUIDPKMixin, Base):
    """The ``resume_versions`` table (database.md §3).

    No ``updated_at`` -- a render is immutable once created, same
    reasoning as ``MatchScoreModel``/``ATSReportModel`` (re-generating
    produces a new row, history retained).
    """

    __tablename__ = "resume_versions"

    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id"))
    job_posting_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("job_postings.id"), nullable=True
    )
    template_id: Mapped[str] = mapped_column(String(36), ForeignKey("templates.id"))
    rendered_pdf_path: Mapped[str] = mapped_column(Text)
    rendered_tex_path: Mapped[str] = mapped_column(Text)
    ats_verification_passed: Mapped[bool] = mapped_column(Boolean)
    ats_extracted_text_path: Mapped[str] = mapped_column(Text)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CoverLetterModel(UUIDPKMixin, Base):
    """The ``cover_letters`` table (database.md §8).

    No ``profile_id`` column -- database.md §8 doesn't define one
    (unlike ``resume_versions``); the profile is reachable indirectly
    via ``resume_version_id -> resume_versions.profile_id`` if ever
    needed. No ``updated_at`` -- immutable once rendered, same as
    ``ResumeVersionModel``.
    """

    __tablename__ = "cover_letters"

    application_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=True
    )
    job_posting_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_postings.id"))
    resume_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("resume_versions.id"))
    template_id: Mapped[str] = mapped_column(String(36), ForeignKey("templates.id"))
    rendered_pdf_path: Mapped[str] = mapped_column(Text)
    rendered_tex_path: Mapped[str] = mapped_column(Text)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
