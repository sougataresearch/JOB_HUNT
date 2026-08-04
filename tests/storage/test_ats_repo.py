"""Round-trip tests for ATSRepo (phases.md Phase 4 acceptance criteria)."""

from sqlalchemy.orm import Session

from jobhunt_core.schemas.ats import ATSReport
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.profile import CandidateProfile
from jobhunt_core.storage.repositories.ats_repo import ATSRepo
from jobhunt_core.storage.repositories.job_repo import JobRepo
from jobhunt_core.storage.repositories.profile_repo import ProfileRepo


def _seed_parents(db_session: Session) -> tuple[str, str]:
    job = JobRepo(db_session).save(
        JobPosting(
            source="greenhouse",
            source_id="1",
            title="Engineer",
            url="https://example.com/1",
        )
    )
    profile = ProfileRepo(db_session).save(CandidateProfile(full_name="Jane Doe"))
    return job.id, profile.id


def test_round_trip_write_then_read(db_session: Session) -> None:
    """A saved report reads back with supported/unsupported gaps intact."""
    job_id, profile_id = _seed_parents(db_session)
    repo = ATSRepo(db_session)
    report = ATSReport(
        job_posting_id=job_id,
        profile_id=profile_id,
        supported_gaps=["Kubernetes (worded as 'container orchestration')"],
        unsupported_gaps=["10 years Rust experience"],
        formatting_warnings=["Non-standard section header: 'What I've Shipped'"],
    )

    saved = repo.save(report)
    fetched = repo.get(saved.id)

    assert fetched is not None
    assert fetched.supported_gaps == ["Kubernetes (worded as 'container orchestration')"]
    assert fetched.unsupported_gaps == ["10 years Rust experience"]
    assert fetched.formatting_warnings == ["Non-standard section header: 'What I've Shipped'"]
