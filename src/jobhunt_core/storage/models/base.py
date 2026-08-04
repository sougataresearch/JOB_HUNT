"""Shared SQLAlchemy declarative base and column mixins (database.md).

Every table uses a UUID string primary key and ``created_at``/
``updated_at`` timestamps (database.md's stated convention) -- the two
mixins below are the one place that's implemented, not repeated per
model.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for every jobhunt_core SQLAlchemy model."""


def new_uuid() -> str:
    """Generate a new UUID4 string for a primary key default."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class UUIDPKMixin:
    """Adds a UUID string primary key (database.md: "id (UUID string, primary key)")."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class TimestampMixin:
    """Adds ``created_at``/``updated_at`` columns (database.md's stated convention)."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
