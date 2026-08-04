"""CandidateProfile SQLAlchemy model (database.md §2)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from jobhunt_core.storage.models.base import Base, TimestampMixin, UUIDPKMixin


class CandidateProfileModel(UUIDPKMixin, TimestampMixin, Base):
    """The ``candidate_profiles`` table.

    ``user_id`` has no foreign key to a ``users`` table -- v1 is
    single-user and ``users`` is unbuilt by design until multi-user
    work is scheduled (database.md §1, decisions.md ADR-0002); it's
    kept as a plain nullable column so the migration path stays a
    migration, not a rewrite.

    Only one profile per user may have ``is_active=True`` at a time
    (database.md §2) -- enforced by a partial unique index, not just
    application logic.
    """

    __tablename__ = "candidate_profiles"
    __table_args__ = (
        Index(
            "ix_candidate_profiles_one_active_per_user",
            "user_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
    )

    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    experience: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    education: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    certifications: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_extraction_confidence: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
