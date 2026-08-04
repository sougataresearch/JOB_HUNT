"""JobRepo — storage access for Company and JobPosting (api.md §7, §2)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from jobhunt_core.schemas.job import Company, JobPosting
from jobhunt_core.storage.models.job import CompanyModel, JobPostingModel


class JobRepo:
    """CRUD access to ``job_postings``, plus get-or-create for companies.

    Company handling lives here rather than in a separate repository:
    it's a small, tightly-coupled lookup table for job postings only
    (tasks.md T4.4 names 6 aggregates, not a 7th for Company).
    """

    def __init__(self, session: Session) -> None:
        """Wrap a SQLAlchemy session; callers own the transaction boundary."""
        self._session = session

    def get(self, id: str) -> JobPosting | None:
        """Look up a posting by id, or ``None`` if it doesn't exist."""
        row = self._session.get(JobPostingModel, id)
        return self._to_schema(row) if row is not None else None

    def get_by_source(self, source: str, source_id: str) -> JobPosting | None:
        """Look up by the ``(source, source_id)`` dedup key (database.md §5)."""
        row = (
            self._session.query(JobPostingModel)
            .filter_by(source=source, source_id=source_id)
            .one_or_none()
        )
        return self._to_schema(row) if row is not None else None

    def list(self, **filters: object) -> list[JobPosting]:
        """Return all postings matching the given column-value filters."""
        query = self._session.query(JobPostingModel)
        for key, value in filters.items():
            query = query.filter(getattr(JobPostingModel, key) == value)
        return [self._to_schema(row) for row in query.all()]

    def save(self, posting: JobPosting) -> JobPosting:
        """Insert a new posting, or update an existing one by ``posting.id``."""
        data = posting.model_dump(exclude={"id", "created_at", "updated_at", "remote_type"})
        data["remote_type"] = posting.remote_type.value

        if posting.id is not None:
            row = self._session.get(JobPostingModel, posting.id)
            if row is None:
                raise ValueError(f"JobPosting {posting.id} not found")
            for key, value in data.items():
                setattr(row, key, value)
        else:
            row = JobPostingModel(**data)
            self._session.add(row)
        self._session.flush()
        return self._to_schema(row)

    def delete(self, id: str) -> None:
        """Delete a posting by id; a no-op if it doesn't exist."""
        row = self._session.get(JobPostingModel, id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    def get_or_create_company(self, name: str, *, domain: str | None = None) -> Company:
        """Return the existing company row matching ``name``, or create one."""
        row = self._session.query(CompanyModel).filter_by(name=name).one_or_none()
        if row is None:
            row = CompanyModel(name=name, domain=domain)
            self._session.add(row)
            self._session.flush()
        return self._company_to_schema(row)

    def _to_schema(self, row: JobPostingModel) -> JobPosting:
        return JobPosting(
            id=row.id,
            user_id=row.user_id,
            company_id=row.company_id,
            source=row.source,
            source_id=row.source_id,
            title=row.title,
            location=row.location,
            remote_type=row.remote_type,  # type: ignore[arg-type]  # pydantic coerces str -> enum
            url=row.url,
            raw_content_path=row.raw_content_path,
            normalized_description=row.normalized_description,
            posted_at=row.posted_at,
            discovered_at=row.discovered_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _company_to_schema(self, row: CompanyModel) -> Company:
        return Company(
            id=row.id,
            name=row.name,
            domain=row.domain,
            notes=row.notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
