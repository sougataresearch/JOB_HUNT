"""MatchScore SQLAlchemy model (database.md §6)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from jobhunt_core.storage.models.base import Base, UUIDPKMixin, utcnow


class MatchScoreModel(UUIDPKMixin, Base):
    """The ``match_scores`` table.

    Re-scoring creates a new row rather than overwriting the prior one
    (database.md §6 -- history retained for regression comparison,
    testing.md), so there's no unique constraint on ``(job_posting_id,
    profile_id)``; an index supports the common lookup instead. No
    ``updated_at`` -- a score is immutable once created.
    """

    __tablename__ = "match_scores"
    __table_args__ = (Index("ix_match_scores_job_profile", "job_posting_id", "profile_id"),)

    job_posting_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_postings.id"))
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id"))
    score: Mapped[float] = mapped_column(Float)
    matched_requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    red_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
