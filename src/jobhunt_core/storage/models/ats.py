"""ATSReport SQLAlchemy model (database.md §7)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from jobhunt_core.storage.models.base import Base, UUIDPKMixin, utcnow


class ATSReportModel(UUIDPKMixin, Base):
    """The ``ats_reports`` table. No ``updated_at`` -- immutable once created."""

    __tablename__ = "ats_reports"
    __table_args__ = (Index("ix_ats_reports_job_profile", "job_posting_id", "profile_id"),)

    job_posting_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_postings.id"))
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id"))
    supported_gaps: Mapped[list[str]] = mapped_column(JSON, default=list)
    unsupported_gaps: Mapped[list[str]] = mapped_column(JSON, default=list)
    formatting_warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
