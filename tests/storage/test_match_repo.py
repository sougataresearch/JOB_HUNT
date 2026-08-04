"""Round-trip tests for MatchRepo (phases.md Phase 4 acceptance criteria)."""

from sqlalchemy.orm import Session

from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.match import MatchScore
from jobhunt_core.schemas.profile import CandidateProfile
from jobhunt_core.storage.repositories.job_repo import JobRepo
from jobhunt_core.storage.repositories.match_repo import MatchRepo
from jobhunt_core.storage.repositories.profile_repo import ProfileRepo


def _seed_parents(db_session: Session) -> tuple[str, str]:
    """Create a valid JobPosting + CandidateProfile (FK enforcement is on)."""
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
    """A saved score reads back with every field intact."""
    job_id, profile_id = _seed_parents(db_session)
    repo = MatchRepo(db_session)
    score = MatchScore(
        job_posting_id=job_id,
        profile_id=profile_id,
        score=87.5,
        matched_requirements=["Python"],
        missing_requirements=["Kubernetes"],
        rationale="Strong Python background, no k8s experience mentioned.",
    )

    saved = repo.save(score)
    fetched = repo.get(saved.id)

    assert fetched is not None
    assert fetched.score == 87.5
    assert fetched.matched_requirements == ["Python"]
    assert fetched.rationale == "Strong Python background, no k8s experience mentioned."
    assert fetched.created_at is not None


def test_rescoring_creates_new_row_not_an_update(db_session: Session) -> None:
    """save() always inserts -- re-scoring keeps history (database.md §6)."""
    job_id, profile_id = _seed_parents(db_session)
    repo = MatchRepo(db_session)
    base = MatchScore(
        job_posting_id=job_id, profile_id=profile_id, score=50.0, rationale="first pass"
    )

    first = repo.save(base)
    second = repo.save(base.model_copy(update={"score": 60.0, "rationale": "re-scored"}))

    assert first.id != second.id
    all_scores = repo.list(job_posting_id=job_id, profile_id=profile_id)
    assert len(all_scores) == 2


def test_foreign_key_enforced_for_missing_job_posting(db_session: Session) -> None:
    """Saving a score against a nonexistent job_posting_id fails (FK enforcement)."""
    from sqlalchemy.exc import IntegrityError

    _, profile_id = _seed_parents(db_session)
    repo = MatchRepo(db_session)
    bad_score = MatchScore(
        job_posting_id="does-not-exist", profile_id=profile_id, score=1.0, rationale="x"
    )

    try:
        repo.save(bad_score)
        raised = False
    except IntegrityError:
        raised = True
        db_session.rollback()

    assert raised
