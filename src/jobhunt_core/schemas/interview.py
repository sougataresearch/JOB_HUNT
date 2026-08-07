"""Interview and InterviewQuestion schemas (database.md §11, §12)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class InterviewType(StrEnum):
    """``interviews.interview_type`` (database.md §11)."""

    PHONE_SCREEN = "phone_screen"
    TECHNICAL = "technical"
    ONSITE = "onsite"
    FINAL = "final"


class QuestionCategory(StrEnum):
    """``interview_questions.category`` (database.md §12)."""

    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    COMPANY = "company"
    ROLE_SPECIFIC = "role_specific"


class Interview(BaseModel):
    """One interview round tied to an application (database.md §11)."""

    id: str | None = None
    application_id: str
    scheduled_at: datetime | None = None
    interview_type: InterviewType
    outcome: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InterviewQuestion(BaseModel):
    """One prepared question + talking points (agents.md §10, database.md §12).

    ``suggested_talking_points`` must be traceable to specific resume
    bullets or posting lines, not invented (rules.md AI Coding Rule 1).
    """

    id: str | None = None
    interview_id: str
    category: QuestionCategory
    question: str
    suggested_talking_points: list[str] = Field(default_factory=list)
    agent_run_id: str | None = None


class InterviewQuestionDraft(BaseModel):
    """One LLM-drafted question, before ``interview_id`` is known (agents.md §10, prompts.md).

    Narrower than ``InterviewQuestion`` -- excludes ``id``/
    ``interview_id``/``agent_run_id``, set by the agent, same
    ``*Extraction``-style pattern as ``MatchScoreExtraction``.
    """

    category: QuestionCategory
    question: str
    suggested_talking_points: list[str] = Field(default_factory=list)


class InterviewPrepExtraction(BaseModel):
    """The Interview Prep Agent's LLM call output (agents.md §10)."""

    questions: list[InterviewQuestionDraft] = Field(default_factory=list)


class InterviewPrepPack(BaseModel):
    """The full agent output: one interview plus its prepared questions (phases.md Phase 15).

    Not a separate DB table -- database.md §12 persists this as
    ``interview_questions`` rows tied to ``interview_id`` (agents.md
    §10's own "Outputs: InterviewPrepPack (database.md §12,
    interview_questions rows)" note); this schema is the richer
    in-memory bundle the agent returns, the same collapsing-into-
    existing-columns pattern ``PDFVerificationResult`` (Phase 11) used.
    """

    interview: Interview
    questions: list[InterviewQuestion] = Field(default_factory=list)
