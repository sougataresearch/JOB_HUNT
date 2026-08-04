"""MatchRepo — storage access for MatchScore (api.md §7)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from jobhunt_core.schemas.match import MatchScore
from jobhunt_core.storage.models.match import MatchScoreModel


class MatchRepo:
    """CRUD access to ``match_scores``.

    ``save()`` always inserts a new row -- scores are immutable
    history (database.md §6, testing.md regression suite); there is
    no update-in-place path even if ``entity.id`` happens to be set.
    """

    def __init__(self, session: Session) -> None:
        """Wrap a SQLAlchemy session; callers own the transaction boundary."""
        self._session = session

    def get(self, id: str) -> MatchScore | None:
        """Look up a score by id, or ``None`` if it doesn't exist."""
        row = self._session.get(MatchScoreModel, id)
        return self._to_schema(row) if row is not None else None

    def list(self, **filters: object) -> list[MatchScore]:
        """Return all scores matching the given column-value filters."""
        query = self._session.query(MatchScoreModel)
        for key, value in filters.items():
            query = query.filter(getattr(MatchScoreModel, key) == value)
        return [self._to_schema(row) for row in query.all()]

    def save(self, score: MatchScore) -> MatchScore:
        """Insert a new score row (never updates an existing one)."""
        data = score.model_dump(exclude={"id", "created_at"})
        row = MatchScoreModel(**data)
        self._session.add(row)
        self._session.flush()
        return self._to_schema(row)

    def delete(self, id: str) -> None:
        """Delete a score by id; a no-op if it doesn't exist."""
        row = self._session.get(MatchScoreModel, id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    def _to_schema(self, row: MatchScoreModel) -> MatchScore:
        return MatchScore(
            id=row.id,
            job_posting_id=row.job_posting_id,
            profile_id=row.profile_id,
            score=row.score,
            matched_requirements=row.matched_requirements,
            missing_requirements=row.missing_requirements,
            red_flags=row.red_flags,
            rationale=row.rationale,
            agent_run_id=row.agent_run_id,
            created_at=row.created_at,
        )
