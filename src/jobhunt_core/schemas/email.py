"""Email schemas (api.md §6, agents.md §8)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class EmailDraftExtraction(BaseModel):
    """The Email Generation Agent's LLM call output (agents.md §8, prompts.md).

    Deliberately excludes ``attachments``/``status`` -- those are
    assembled by the agent directly from ``ResumeVersion``/
    ``CoverLetter`` file paths, never LLM-authored (agents.md §8
    Metrics: "Attachment-reference correctness (automated check, not
    an LLM judgment)").
    """

    to: str | None = None
    subject: str
    body: str


class EmailDraft(BaseModel):
    """The application submission email draft (api.md §6).

    ``status`` is always ``"draft"`` -- there is deliberately no
    ``send()`` method anywhere in this API surface (api.md §6, PRD.md
    §9); sending is a human action outside this system.
    """

    to: str | None
    subject: str
    body: str
    attachments: list[Path] = Field(default_factory=list)
    status: Literal["draft"] = "draft"
