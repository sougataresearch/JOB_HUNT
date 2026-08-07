"""Round-trip tests for DocumentRepo (phases.md Phase 11/12 acceptance criteria)."""

from sqlalchemy.orm import Session

from jobhunt_core.schemas.document import CoverLetter, ResumeVersion
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.profile import CandidateProfile
from jobhunt_core.storage.repositories.document_repo import DocumentRepo
from jobhunt_core.storage.repositories.job_repo import JobRepo
from jobhunt_core.storage.repositories.profile_repo import ProfileRepo


def test_get_or_create_template_is_idempotent(db_session: Session) -> None:
    """Calling get_or_create_template twice with the same (kind, name) returns the same row."""
    repo = DocumentRepo(db_session)

    first = repo.get_or_create_template(
        kind="resume", name="resume", file_path="cv/resume.tex.jinja"
    )
    second = repo.get_or_create_template(
        kind="resume", name="resume", file_path="cv/resume.tex.jinja"
    )

    assert first.id == second.id


def test_get_or_create_template_distinguishes_by_kind(db_session: Session) -> None:
    """Same name, different kind -> two distinct template rows."""
    repo = DocumentRepo(db_session)

    resume = repo.get_or_create_template(kind="resume", name="default", file_path="cv/a.tex.jinja")
    cover_letter = repo.get_or_create_template(
        kind="cover_letter", name="default", file_path="cover_letter/a.tex.jinja"
    )

    assert resume.id != cover_letter.id


def test_get_template_missing_returns_none(db_session: Session) -> None:
    """A template id that doesn't exist returns None, not an error."""
    repo = DocumentRepo(db_session)

    assert repo.get_template("does-not-exist") is None


def test_resume_version_round_trip(db_session: Session) -> None:
    """A saved resume_version reads back with every field intact."""
    profile = ProfileRepo(db_session).save(CandidateProfile(full_name="Jane Doe"))
    posting = JobRepo(db_session).save(
        JobPosting(
            source="greenhouse", source_id="1", title="Engineer", url="https://example.com/1"
        )
    )
    repo = DocumentRepo(db_session)
    template = repo.get_or_create_template(
        kind="resume", name="resume", file_path="cv/resume.tex.jinja"
    )

    saved = repo.save_resume_version(
        ResumeVersion(
            profile_id=profile.id,
            job_posting_id=posting.id,
            template_id=template.id,
            rendered_pdf_path="/data/documents/resumes/x/resume.pdf",
            rendered_tex_path="/data/documents/resumes/x/resume.tex",
            ats_verification_passed=True,
            ats_extracted_text_path="/data/documents/resumes/x/resume.extracted.txt",
        )
    )

    fetched = repo.get_resume_version(saved.id)

    assert fetched is not None
    assert fetched.profile_id == profile.id
    assert fetched.job_posting_id == posting.id
    assert fetched.template_id == template.id
    assert fetched.ats_verification_passed is True


def test_list_resume_versions_filters_by_profile(db_session: Session) -> None:
    """list_resume_versions(**filters) narrows to matching rows."""
    profile_a = ProfileRepo(db_session).save(CandidateProfile(full_name="A"))
    profile_b = ProfileRepo(db_session).save(CandidateProfile(full_name="B"))
    posting = JobRepo(db_session).save(
        JobPosting(
            source="greenhouse", source_id="1", title="Engineer", url="https://example.com/1"
        )
    )
    repo = DocumentRepo(db_session)
    template = repo.get_or_create_template(kind="resume", name="resume", file_path="cv/r.tex.jinja")

    def _save(profile_id: str) -> None:
        repo.save_resume_version(
            ResumeVersion(
                profile_id=profile_id,
                job_posting_id=posting.id,
                template_id=template.id,
                rendered_pdf_path="p.pdf",
                rendered_tex_path="p.tex",
                ats_verification_passed=True,
                ats_extracted_text_path="p.txt",
            )
        )

    _save(profile_a.id)
    _save(profile_a.id)
    _save(profile_b.id)

    results = repo.list_resume_versions(profile_id=profile_a.id)

    assert len(results) == 2
    assert all(r.profile_id == profile_a.id for r in results)


def test_cover_letter_round_trip(db_session: Session) -> None:
    """A saved cover_letter reads back with every field intact."""
    profile = ProfileRepo(db_session).save(CandidateProfile(full_name="Jane Doe"))
    posting = JobRepo(db_session).save(
        JobPosting(
            source="greenhouse", source_id="1", title="Engineer", url="https://example.com/1"
        )
    )
    repo = DocumentRepo(db_session)
    resume_template = repo.get_or_create_template(
        kind="resume", name="resume", file_path="cv/resume.tex.jinja"
    )
    resume_version = repo.save_resume_version(
        ResumeVersion(
            profile_id=profile.id,
            job_posting_id=posting.id,
            template_id=resume_template.id,
            rendered_pdf_path="/data/documents/resumes/x/resume.pdf",
            rendered_tex_path="/data/documents/resumes/x/resume.tex",
            ats_verification_passed=True,
            ats_extracted_text_path="/data/documents/resumes/x/resume.extracted.txt",
        )
    )
    cover_letter_template = repo.get_or_create_template(
        kind="cover_letter", name="cover_letter", file_path="cover_letter/cover_letter.tex.jinja"
    )

    saved = repo.save_cover_letter(
        CoverLetter(
            job_posting_id=posting.id,
            resume_version_id=resume_version.id,
            template_id=cover_letter_template.id,
            rendered_pdf_path="/data/documents/cover_letters/x/cover_letter.pdf",
            rendered_tex_path="/data/documents/cover_letters/x/cover_letter.tex",
        )
    )

    fetched = repo.get_cover_letter(saved.id)

    assert fetched is not None
    assert fetched.job_posting_id == posting.id
    assert fetched.resume_version_id == resume_version.id
    assert fetched.template_id == cover_letter_template.id
    assert fetched.application_id is None


def test_get_cover_letter_missing_returns_none(db_session: Session) -> None:
    """A cover letter id that doesn't exist returns None, not an error."""
    repo = DocumentRepo(db_session)

    assert repo.get_cover_letter("does-not-exist") is None


def test_list_cover_letters_filters_by_job_posting(db_session: Session) -> None:
    """list_cover_letters(**filters) narrows to matching rows."""
    profile = ProfileRepo(db_session).save(CandidateProfile(full_name="Jane Doe"))
    posting_a = JobRepo(db_session).save(
        JobPosting(source="greenhouse", source_id="1", title="A", url="https://example.com/1")
    )
    posting_b = JobRepo(db_session).save(
        JobPosting(source="greenhouse", source_id="2", title="B", url="https://example.com/2")
    )
    repo = DocumentRepo(db_session)
    resume_template = repo.get_or_create_template(
        kind="resume", name="r", file_path="cv/r.tex.jinja"
    )
    cover_letter_template = repo.get_or_create_template(
        kind="cover_letter", name="cl", file_path="cover_letter/cl.tex.jinja"
    )

    def _save(job_posting_id: str) -> None:
        resume_version = repo.save_resume_version(
            ResumeVersion(
                profile_id=profile.id,
                job_posting_id=job_posting_id,
                template_id=resume_template.id,
                rendered_pdf_path="r.pdf",
                rendered_tex_path="r.tex",
                ats_verification_passed=True,
                ats_extracted_text_path="r.txt",
            )
        )
        repo.save_cover_letter(
            CoverLetter(
                job_posting_id=job_posting_id,
                resume_version_id=resume_version.id,
                template_id=cover_letter_template.id,
                rendered_pdf_path="cl.pdf",
                rendered_tex_path="cl.tex",
            )
        )

    _save(posting_a.id)
    _save(posting_a.id)
    _save(posting_b.id)

    results = repo.list_cover_letters(job_posting_id=posting_a.id)

    assert len(results) == 2
    assert all(r.job_posting_id == posting_a.id for r in results)
