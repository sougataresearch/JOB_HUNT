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
