"""Application and ApplicationEvent SQLAlchemy models (database.md §9, §10)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from jobhunt_core.storage.models.base import Base, TimestampMixin, UUIDPKMixin, utcnow


class ApplicationModel(UUIDPKMixin, TimestampMixin, Base):
    """The ``applications`` table -- one application per posting.

    Not yet columns here (added when their owning phase lands, per
    progress_log.md): ``resume_version_id``, ``cover_letter_id``
    (Phase 11/12).
    """

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("job_posting_id", name="uq_applications_job_posting"),)

    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    job_posting_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_postings.id"))
    status: Mapped[str] = mapped_column(String(32), default="drafted")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ApplicationEventModel(UUIDPKMixin, Base):
    """The ``application_events`` table -- append-only status history.

    Never updated or deleted (design.md §3 -- soft state, hard
    history): only ``ApplicationRepo.add_event()`` inserts rows here.
    """

    __tablename__ = "application_events"

    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"))
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(16), default="user")
