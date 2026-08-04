"""Round-trip tests for ProfileRepo (phases.md Phase 4 acceptance criteria)."""

from sqlalchemy.orm import Session

from jobhunt_core.schemas.profile import CandidateProfile, EducationEntry, ExperienceEntry
from jobhunt_core.storage.repositories.profile_repo import ProfileRepo


def _sample_profile() -> CandidateProfile:
    return CandidateProfile(
        user_id="user-1",
        full_name="Jane Doe",
        email="jane@example.com",
        skills=["python", "sql"],
        experience=[ExperienceEntry(title="Engineer", company="Acme", bullets=["Built things"])],
        education=[EducationEntry(institution="State U", degree="BSc")],
        certifications=["AWS Certified"],
        raw_extraction_confidence={"email": 0.95},
    )


def test_round_trip_write_then_read(db_session: Session) -> None:
    """A saved profile reads back with every field intact."""
    repo = ProfileRepo(db_session)
    saved = repo.save(_sample_profile())

    fetched = repo.get(saved.id)

    assert fetched is not None
    assert fetched.full_name == "Jane Doe"
    assert fetched.email == "jane@example.com"
    assert fetched.skills == ["python", "sql"]
    assert fetched.experience == [
        ExperienceEntry(title="Engineer", company="Acme", bullets=["Built things"])
    ]
    assert fetched.education == [EducationEntry(institution="State U", degree="BSc")]
    assert fetched.raw_extraction_confidence == {"email": 0.95}
    assert fetched.is_active is True
    assert fetched.created_at is not None


def test_get_missing_returns_none(db_session: Session) -> None:
    """Looking up a nonexistent id returns None, not an exception."""
    repo = ProfileRepo(db_session)

    assert repo.get("does-not-exist") is None


def test_save_new_active_profile_deactivates_prior_active(db_session: Session) -> None:
    """Saving a second active profile for the same user deactivates the first."""
    repo = ProfileRepo(db_session)
    first = repo.save(_sample_profile())
    assert first.is_active is True

    second = repo.save(_sample_profile())

    refetched_first = repo.get(first.id)
    assert refetched_first is not None
    assert refetched_first.is_active is False
    assert second.is_active is True
    assert repo.get_active(user_id="user-1").id == second.id


def test_update_existing_profile(db_session: Session) -> None:
    """Saving a profile with an existing id updates the row in place."""
    repo = ProfileRepo(db_session)
    saved = repo.save(_sample_profile())

    saved.full_name = "Jane R. Doe"
    updated = repo.save(saved)

    assert updated.id == saved.id
    refetched = repo.get(saved.id)
    assert refetched is not None
    assert refetched.full_name == "Jane R. Doe"


def test_delete(db_session: Session) -> None:
    """A deleted profile is no longer retrievable."""
    repo = ProfileRepo(db_session)
    saved = repo.save(_sample_profile())

    repo.delete(saved.id)

    assert repo.get(saved.id) is None
