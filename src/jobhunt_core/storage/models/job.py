"""Company and JobPosting SQLAlchemy models (database.md §4, §5)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from jobhunt_core.storage.models.base import Base, TimestampMixin, UUIDPKMixin


class CompanyModel(UUIDPKMixin, TimestampMixin, Base):
    """The ``companies`` table."""

    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("name", name="uq_companies_name"),)

    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class JobPostingModel(UUIDPKMixin, TimestampMixin, Base):
    """The ``job_postings`` table.

    Unique on ``(source, source_id)`` -- the primary dedup key
    (database.md §5, agents.md §3 Job Search Agent). ``search_run_id``
    is not yet a column (added in Phase 7 once ``search_runs`` exists).
    """

    __tablename__ = "job_postings"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_job_postings_source"),)

    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_type: Mapped[str] = mapped_column(String(16), default="unknown")
    url: Mapped[str] = mapped_column(Text)
    raw_content_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_description: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
