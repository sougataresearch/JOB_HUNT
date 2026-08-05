"""ProfileRepo — the only storage-access surface for CandidateProfile (api.md §7)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from jobhunt_core.errors import StorageError
from jobhunt_core.schemas.profile import CandidateProfile, EducationEntry, ExperienceEntry
from jobhunt_core.storage.models.profile import CandidateProfileModel


class ProfileRepo:
    """CRUD access to ``candidate_profiles``."""

    def __init__(self, session: Session) -> None:
        """Wrap a SQLAlchemy session; callers own the transaction boundary."""
        self._session = session

    def get(self, id: str) -> CandidateProfile | None:
        """Look up a profile by id, or ``None`` if it doesn't exist."""
        row = self._session.get(CandidateProfileModel, id)
        return self._to_schema(row) if row is not None else None

    def get_active(self, user_id: str | None = None) -> CandidateProfile | None:
        """Return the current active profile for ``user_id`` (database.md §2)."""
        row = (
            self._session.query(CandidateProfileModel)
            .filter_by(is_active=True, user_id=user_id)
            .one_or_none()
        )
        return self._to_schema(row) if row is not None else None

    def list(self, **filters: object) -> list[CandidateProfile]:
        """Return all profiles matching the given column-value filters."""
        query = self._session.query(CandidateProfileModel)
        for key, value in filters.items():
            query = query.filter(getattr(CandidateProfileModel, key) == value)
        return [self._to_schema(row) for row in query.all()]

    def save(self, profile: CandidateProfile) -> CandidateProfile:
        """Insert a new profile, or update an existing one by ``profile.id``.

        Saving a new *active* profile first deactivates any existing
        active profile for the same user, so the DB-level partial
        unique index (database.md §2's "exactly one active profile"
        constraint) is never violated by application code.
        """
        if profile.id is None and profile.is_active:
            self._deactivate_existing_active(profile.user_id)

        data = profile.model_dump(
            exclude={"id", "created_at", "updated_at", "experience", "education"}
        )
        data["experience"] = [e.model_dump() for e in profile.experience]
        data["education"] = [e.model_dump() for e in profile.education]

        if profile.id is not None:
            row = self._session.get(CandidateProfileModel, profile.id)
            if row is None:
                raise StorageError(f"CandidateProfile {profile.id} not found")
            for key, value in data.items():
                setattr(row, key, value)
        else:
            row = CandidateProfileModel(**data)
            self._session.add(row)
        self._session.flush()
        return self._to_schema(row)

    def delete(self, id: str) -> None:
        """Delete a profile by id; a no-op if it doesn't exist."""
        row = self._session.get(CandidateProfileModel, id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    def _deactivate_existing_active(self, user_id: str | None) -> None:
        existing = (
            self._session.query(CandidateProfileModel)
            .filter_by(is_active=True, user_id=user_id)
            .one_or_none()
        )
        if existing is not None:
            existing.is_active = False
            self._session.flush()

    def _to_schema(self, row: CandidateProfileModel) -> CandidateProfile:
        return CandidateProfile(
            id=row.id,
            user_id=row.user_id,
            source_file_path=row.source_file_path,
            full_name=row.full_name,
            email=row.email,
            phone=row.phone,
            location=row.location,
            summary=row.summary,
            skills=row.skills,
            experience=[ExperienceEntry(**e) for e in row.experience],
            education=[EducationEntry(**e) for e in row.education],
            certifications=row.certifications,
            raw_extraction_confidence=row.raw_extraction_confidence,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
