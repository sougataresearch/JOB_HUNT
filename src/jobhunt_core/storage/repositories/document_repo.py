"""DocumentRepo — storage access for Template, ResumeVersion, and CoverLetter (api.md §7).

All three live in one repo (like ``Company``/``SearchRun`` inside
``JobRepo``, Phases 4/7): small, tightly-coupled aggregates -- every
``ResumeVersion``/``CoverLetter`` references exactly one ``Template``,
a ``CoverLetter`` also references exactly one ``ResumeVersion``, and
none is large enough to justify its own ``RepositoryBundle`` slot
(Phase 12: reusing this repo rather than adding an 8th
``RepositoryBundle`` field avoids repeating Phase 11's cross-cutting
change across every existing test file for a table this tightly
coupled to the two already here).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from jobhunt_core.schemas.document import CoverLetter, ResumeVersion, Template
from jobhunt_core.storage.models.document import (
    CoverLetterModel,
    ResumeVersionModel,
    TemplateModel,
)


class DocumentRepo:
    """CRUD access to ``templates``, ``resume_versions``, and ``cover_letters``."""

    def __init__(self, session: Session) -> None:
        """Wrap a SQLAlchemy session; callers own the transaction boundary."""
        self._session = session

    def get_or_create_template(
        self, *, kind: str, name: str, file_path: str, description: str = ""
    ) -> Template:
        """Return the existing template matching ``(kind, name)``, or register one.

        Registration is idempotent by design (matching
        ``JobRepo.get_or_create_company``): re-running the agent
        against the same template file never creates duplicate rows.
        """
        row = self._session.query(TemplateModel).filter_by(kind=kind, name=name).one_or_none()
        if row is None:
            row = TemplateModel(kind=kind, name=name, file_path=file_path, description=description)
            self._session.add(row)
            self._session.flush()
        return self._template_to_schema(row)

    def get_template(self, id: str) -> Template | None:
        """Look up a template by id, or ``None`` if it doesn't exist."""
        row = self._session.get(TemplateModel, id)
        return self._template_to_schema(row) if row is not None else None

    def save_resume_version(self, resume_version: ResumeVersion) -> ResumeVersion:
        """Insert a new resume_versions row (never updates an existing one -- immutable history)."""
        data = resume_version.model_dump(exclude={"id", "created_at"})
        row = ResumeVersionModel(**data)
        self._session.add(row)
        self._session.flush()
        return self._resume_version_to_schema(row)

    def get_resume_version(self, id: str) -> ResumeVersion | None:
        """Look up a resume version by id, or ``None`` if it doesn't exist."""
        row = self._session.get(ResumeVersionModel, id)
        return self._resume_version_to_schema(row) if row is not None else None

    def list_resume_versions(self, **filters: object) -> list[ResumeVersion]:
        """Return all resume versions matching the given column-value filters."""
        query = self._session.query(ResumeVersionModel)
        for key, value in filters.items():
            query = query.filter(getattr(ResumeVersionModel, key) == value)
        return [self._resume_version_to_schema(row) for row in query.all()]

    def save_cover_letter(self, cover_letter: CoverLetter) -> CoverLetter:
        """Insert a new cover_letters row (never updates an existing one -- immutable history)."""
        data = cover_letter.model_dump(exclude={"id", "created_at"})
        row = CoverLetterModel(**data)
        self._session.add(row)
        self._session.flush()
        return self._cover_letter_to_schema(row)

    def get_cover_letter(self, id: str) -> CoverLetter | None:
        """Look up a cover letter by id, or ``None`` if it doesn't exist."""
        row = self._session.get(CoverLetterModel, id)
        return self._cover_letter_to_schema(row) if row is not None else None

    def list_cover_letters(self, **filters: object) -> list[CoverLetter]:
        """Return all cover letters matching the given column-value filters."""
        query = self._session.query(CoverLetterModel)
        for key, value in filters.items():
            query = query.filter(getattr(CoverLetterModel, key) == value)
        return [self._cover_letter_to_schema(row) for row in query.all()]

    def _template_to_schema(self, row: TemplateModel) -> Template:
        return Template(
            id=row.id,
            kind=row.kind,  # type: ignore[arg-type]  # pydantic coerces str -> Literal
            name=row.name,
            file_path=row.file_path,
            description=row.description,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _resume_version_to_schema(self, row: ResumeVersionModel) -> ResumeVersion:
        return ResumeVersion(
            id=row.id,
            profile_id=row.profile_id,
            job_posting_id=row.job_posting_id,
            template_id=row.template_id,
            rendered_pdf_path=row.rendered_pdf_path,
            rendered_tex_path=row.rendered_tex_path,
            ats_verification_passed=row.ats_verification_passed,
            ats_extracted_text_path=row.ats_extracted_text_path,
            agent_run_id=row.agent_run_id,
            created_at=row.created_at,
        )

    def _cover_letter_to_schema(self, row: CoverLetterModel) -> CoverLetter:
        return CoverLetter(
            id=row.id,
            application_id=row.application_id,
            job_posting_id=row.job_posting_id,
            resume_version_id=row.resume_version_id,
            template_id=row.template_id,
            rendered_pdf_path=row.rendered_pdf_path,
            rendered_tex_path=row.rendered_tex_path,
            agent_run_id=row.agent_run_id,
            created_at=row.created_at,
        )
