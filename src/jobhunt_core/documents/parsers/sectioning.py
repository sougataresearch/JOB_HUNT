"""Shared best-effort section-splitting heuristic for CV parsers (tasks.md T5.1).

This is a structural aid only -- the Resume Analysis Agent (agents.md
§1) does the actual field extraction via an LLM using ``raw_text``
and/or these sections as context. A wrong or missing section split
here never causes the agent to invent content; it just means less
structure to work with.
"""

from __future__ import annotations

import re

_KNOWN_SECTION_NAMES = frozenset(
    {
        "summary",
        "experience",
        "work experience",
        "employment history",
        "education",
        "skills",
        "certifications",
        "projects",
        "publications",
    }
)

_MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*(?P<title>.+?)\s*#*\s*$")


def split_markdown_sections(raw_text: str) -> dict[str, str]:
    """Split Markdown text into sections keyed by heading text."""
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in raw_text.splitlines():
        match = _MARKDOWN_HEADING_RE.match(line)
        if match:
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = match.group("title").strip()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def split_plaintext_sections(raw_text: str) -> dict[str, str]:
    """Best-effort section split for plain extracted text (PDF/DOCX).

    Looks for a standalone short line matching one of a small set of
    common resume section names (case-insensitive) and treats it as a
    heading. Content before the first recognized heading is not
    included in ``sections`` (it remains fully present in ``raw_text``).
    """
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in raw_text.splitlines():
        stripped = line.strip()
        normalized = stripped.lower().rstrip(":")
        if normalized in _KNOWN_SECTION_NAMES and len(stripped) < 40:
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = stripped.rstrip(":")
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections
