"""ATSRepo — storage access for ATSReport (api.md §7)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from jobhunt_core.schemas.ats import ATSReport
from jobhunt_core.storage.models.ats import ATSReportModel


class ATSRepo:
    """CRUD access to ``ats_reports``. Immutable history, like ``MatchRepo``."""

    def __init__(self, session: Session) -> None:
        """Wrap a SQLAlchemy session; callers own the transaction boundary."""
        self._session = session

    def get(self, id: str) -> ATSReport | None:
        """Look up a report by id, or ``None`` if it doesn't exist."""
        row = self._session.get(ATSReportModel, id)
        return self._to_schema(row) if row is not None else None

    def list(self, **filters: object) -> list[ATSReport]:
        """Return all reports matching the given column-value filters."""
        query = self._session.query(ATSReportModel)
        for key, value in filters.items():
            query = query.filter(getattr(ATSReportModel, key) == value)
        return [self._to_schema(row) for row in query.all()]

    def save(self, report: ATSReport) -> ATSReport:
        """Insert a new report row (never updates an existing one)."""
        data = report.model_dump(exclude={"id", "created_at"})
        row = ATSReportModel(**data)
        self._session.add(row)
        self._session.flush()
        return self._to_schema(row)

    def delete(self, id: str) -> None:
        """Delete a report by id; a no-op if it doesn't exist."""
        row = self._session.get(ATSReportModel, id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    def _to_schema(self, row: ATSReportModel) -> ATSReport:
        return ATSReport(
            id=row.id,
            job_posting_id=row.job_posting_id,
            profile_id=row.profile_id,
            supported_gaps=row.supported_gaps,
            unsupported_gaps=row.unsupported_gaps,
            formatting_warnings=row.formatting_warnings,
            agent_run_id=row.agent_run_id,
            created_at=row.created_at,
        )
