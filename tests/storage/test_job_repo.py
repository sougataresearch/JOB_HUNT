"""Round-trip tests for JobRepo (phases.md Phase 4 acceptance criteria)."""

from sqlalchemy.orm import Session

from jobhunt_core.schemas.job import JobPosting, RemoteType
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
