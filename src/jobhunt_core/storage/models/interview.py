"""Interview and InterviewQuestion SQLAlchemy models (database.md §11, §12)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from jobhunt_core.storage.models.base import Base, TimestampMixin, UUIDPKMixin


class InterviewModel(UUIDPKMixin, TimestampMixin, Base):
    """The ``interviews`` table."""

    __tablename__ = "interviews"

    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interview_type: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)


class InterviewQuestionModel(UUIDPKMixin, Base):
    """The ``interview_questions`` table."""

    __tablename__ = "interview_questions"

    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"))
    category: Mapped[str] = mapped_column(String(32))
    question: Mapped[str] = mapped_column(Text)
    suggested_talking_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
