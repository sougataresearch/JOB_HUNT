"""InterviewRepo — storage access for Interview + InterviewQuestion (api.md §7)."""

from __future__ import annotations

import builtins  # see list_questions() docstring below

from sqlalchemy.orm import Session

from jobhunt_core.errors import StorageError
from jobhunt_core.schemas.interview import Interview, InterviewQuestion
from jobhunt_core.storage.models.interview import InterviewModel, InterviewQuestionModel


class InterviewRepo:
    """CRUD access to ``interviews``, plus their prepared questions."""

    def __init__(self, session: Session) -> None:
        """Wrap a SQLAlchemy session; callers own the transaction boundary."""
        self._session = session

    def get(self, id: str) -> Interview | None:
        """Look up an interview by id, or ``None`` if it doesn't exist."""
        row = self._session.get(InterviewModel, id)
        return self._to_schema(row) if row is not None else None

    def list(self, **filters: object) -> list[Interview]:
        """Return all interviews matching the given column-value filters."""
        query = self._session.query(InterviewModel)
        for key, value in filters.items():
            query = query.filter(getattr(InterviewModel, key) == value)
        return [self._to_schema(row) for row in query.all()]

    def save(self, interview: Interview) -> Interview:
        """Insert a new interview, or update an existing one by ``interview.id``."""
        data = interview.model_dump(exclude={"id", "created_at", "updated_at", "interview_type"})
        data["interview_type"] = interview.interview_type.value

        if interview.id is not None:
            row = self._session.get(InterviewModel, interview.id)
            if row is None:
                raise StorageError(f"Interview {interview.id} not found")
            for key, value in data.items():
                setattr(row, key, value)
        else:
            row = InterviewModel(**data)
            self._session.add(row)
        self._session.flush()
        return self._to_schema(row)

    def delete(self, id: str) -> None:
        """Delete an interview by id; a no-op if it doesn't exist."""
        row = self._session.get(InterviewModel, id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    def add_question(self, question: InterviewQuestion) -> InterviewQuestion:
        """Insert one prepared interview question."""
        data = question.model_dump(exclude={"id", "category"})
        row = InterviewQuestionModel(category=question.category.value, **data)
        self._session.add(row)
        self._session.flush()
        return self._question_to_schema(row)

    def list_questions(self, interview_id: str) -> builtins.list[InterviewQuestion]:
        """Return every prepared question for an interview.

        Return type is qualified as ``builtins.list`` because this
        class already defines a method named ``list`` earlier in the
        body -- mypy resolves a bare ``list[...]`` written after that
        point against the method, not the builtin type, and rejects it
        ("Function ... .list is not valid as a type"). Confirmed by
        running mypy, not assumed.
        """
        rows = (
            self._session.query(InterviewQuestionModel).filter_by(interview_id=interview_id).all()
        )
        return [self._question_to_schema(row) for row in rows]

    def _to_schema(self, row: InterviewModel) -> Interview:
        return Interview(
            id=row.id,
            application_id=row.application_id,
            scheduled_at=row.scheduled_at,
            interview_type=row.interview_type,  # type: ignore[arg-type]
            outcome=row.outcome,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _question_to_schema(self, row: InterviewQuestionModel) -> InterviewQuestion:
        return InterviewQuestion(
            id=row.id,
            interview_id=row.interview_id,
            category=row.category,  # type: ignore[arg-type]
            question=row.question,
            suggested_talking_points=row.suggested_talking_points,
            agent_run_id=row.agent_run_id,
        )
