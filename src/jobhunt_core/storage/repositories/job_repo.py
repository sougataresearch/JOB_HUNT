"""JobRepo — storage access for Company, JobPosting, and SearchRun (api.md §7, §2)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from jobhunt_core.errors import StorageError
from jobhunt_core.schemas.job import Company, JobPosting, SearchRun
from jobhunt_core.storage.models.base import utcnow
from jobhunt_core.storage.models.job import CompanyModel, JobPostingModel, SearchRunModel


class JobRepo:
    """CRUD access to ``job_postings``, plus get-or-create for companies and search runs.

    Company and SearchRun handling live here rather than in separate
    repositories: both are small, tightly-coupled to job postings and
    the Job Search Agent's own execution (tasks.md T4.4 names 6
    aggregates in ``RepositoryBundle``, not one apiece for these two —
    same reasoning already applied to ``Company`` in Phase 4, extended
    to ``SearchRun`` in Phase 7).
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
                raise StorageError(f"JobPosting {posting.id} not found")
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

    def create_search_run(self, search_run: SearchRun) -> SearchRun:
        """Insert a new ``search_runs`` row, e.g. at the start of a Job Search Agent run.

        ``search_run.started_at`` should already be set by the caller
        (e.g. ``datetime.now(UTC)``) -- passing ``None`` explicitly
        overrides the column's server-side default rather than
        triggering it.
        """
        data = search_run.model_dump(exclude={"id", "completed_at"})
        row = SearchRunModel(**data)
        self._session.add(row)
        self._session.flush()
        return self._search_run_to_schema(row)

    def complete_search_run(
        self, id: str, *, postings_found: int, postings_deduped_new: int
    ) -> SearchRun:
        """Record a search run's outcome and mark it completed."""
        row = self._session.get(SearchRunModel, id)
        if row is None:
            raise StorageError(f"SearchRun {id} not found")
        row.postings_found = postings_found
        row.postings_deduped_new = postings_deduped_new
        row.completed_at = utcnow()
        self._session.flush()
        return self._search_run_to_schema(row)

    def get_search_run(self, id: str) -> SearchRun | None:
        """Look up a search run by id, or ``None`` if it doesn't exist."""
        row = self._session.get(SearchRunModel, id)
        return self._search_run_to_schema(row) if row is not None else None

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
            search_run_id=row.search_run_id,
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

    def _search_run_to_schema(self, row: SearchRunModel) -> SearchRun:
        return SearchRun(
            id=row.id,
            user_id=row.user_id,
            query=row.query,  # type: ignore[arg-type]  # pydantic parses dict -> SearchQuery
            sources_queried=row.sources_queried,
            postings_found=row.postings_found,
            postings_deduped_new=row.postings_deduped_new,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )
