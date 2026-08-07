"""Round-trip tests for JobRepo (phases.md Phase 4 and Phase 7 acceptance criteria)."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from jobhunt_core.schemas.job import JobPosting, RemoteType, SearchQuery, SearchRun
from jobhunt_core.storage.repositories.job_repo import JobRepo


def _sample_posting(**overrides: object) -> JobPosting:
    defaults: dict = dict(
        source="greenhouse",
        source_id="12345",
        title="Senior Backend Engineer",
        location="Remote",
        remote_type=RemoteType.REMOTE,
        url="https://example.com/jobs/12345",
        normalized_description="We need a backend engineer.",
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


def test_round_trip_write_then_read(db_session: Session) -> None:
    """A saved posting reads back with every field intact, including the enum."""
    repo = JobRepo(db_session)
    saved = repo.save(_sample_posting())

    fetched = repo.get(saved.id)

    assert fetched is not None
    assert fetched.title == "Senior Backend Engineer"
    assert fetched.remote_type == RemoteType.REMOTE
    assert fetched.source == "greenhouse"
    assert fetched.source_id == "12345"


def test_get_by_source_dedup_key(db_session: Session) -> None:
    """get_by_source() resolves the (source, source_id) dedup key (database.md §5)."""
    repo = JobRepo(db_session)
    saved = repo.save(_sample_posting())

    found = repo.get_by_source("greenhouse", "12345")

    assert found is not None
    assert found.id == saved.id


def test_get_or_create_company_is_idempotent(db_session: Session) -> None:
    """Calling get_or_create_company twice with the same name returns the same row."""
    repo = JobRepo(db_session)

    first = repo.get_or_create_company("Acme Corp", domain="acme.com")
    second = repo.get_or_create_company("Acme Corp")

    assert first.id == second.id
    assert second.domain == "acme.com"


def test_posting_can_reference_company(db_session: Session) -> None:
    """A posting's company_id round-trips correctly."""
    repo = JobRepo(db_session)
    company = repo.get_or_create_company("Acme Corp")

    saved = repo.save(_sample_posting(company_id=company.id))
    fetched = repo.get(saved.id)

    assert fetched is not None
    assert fetched.company_id == company.id


def test_delete(db_session: Session) -> None:
    """A deleted posting is no longer retrievable."""
    repo = JobRepo(db_session)
    saved = repo.save(_sample_posting())

    repo.delete(saved.id)

    assert repo.get(saved.id) is None


def test_posting_can_reference_search_run(db_session: Session) -> None:
    """A posting's search_run_id FK round-trips correctly (database.md §17, Phase 7)."""
    repo = JobRepo(db_session)
    search_run = repo.create_search_run(
        SearchRun(query=SearchQuery(keywords=["python"]), started_at=datetime.now(UTC))
    )

    saved = repo.save(_sample_posting(search_run_id=search_run.id))
    fetched = repo.get(saved.id)

    assert fetched is not None
    assert fetched.search_run_id == search_run.id


def test_search_run_round_trip_and_completion(db_session: Session) -> None:
    """create_search_run then complete_search_run persists counts and completed_at."""
    repo = JobRepo(db_session)
    query = SearchQuery(keywords=["python"], locations=["remote"])
    created = repo.create_search_run(
        SearchRun(query=query, sources_queried=["greenhouse"], started_at=datetime.now(UTC))
    )

    assert created.id is not None
    assert created.completed_at is None
    fetched_before = repo.get_search_run(created.id)
    assert fetched_before is not None
    assert fetched_before.query == query
    assert fetched_before.sources_queried == ["greenhouse"]

    completed = repo.complete_search_run(created.id, postings_found=5, postings_deduped_new=3)

    assert completed.postings_found == 5
    assert completed.postings_deduped_new == 3
    assert completed.completed_at is not None


def test_get_search_run_missing_returns_none(db_session: Session) -> None:
    """A search run id that doesn't exist returns None, not an error."""
    repo = JobRepo(db_session)

    assert repo.get_search_run("does-not-exist") is None
