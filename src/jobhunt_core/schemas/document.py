"""ParsedDocument — the output of CV parsing (api.md §1 CV Parser API)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ParsedDocument(BaseModel):
    """Raw text plus a best-effort section split from a parsed CV file."""

    raw_text: str
    sections: dict[str, str] = Field(default_factory=dict)
    source_format: Literal["pdf", "docx", "markdown"]
