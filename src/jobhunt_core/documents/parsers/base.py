"""CVParser Protocol + registry (api.md §1 CV Parser API)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from jobhunt_core.errors import UnsupportedFormatError
from jobhunt_core.schemas.document import ParsedDocument


@runtime_checkable
class CVParser(Protocol):
    """The contract every CV parser implements."""

    def supports(self, file_path: Path) -> bool:
        """Return whether this parser can handle ``file_path``."""
        ...

    def parse(self, file_path: Path) -> ParsedDocument:
        """Parse ``file_path`` into a ``ParsedDocument``."""
        ...


_PARSERS: list[CVParser] = []


def register_parser(parser: CVParser) -> None:
    """Register a parser instance.

    Parsers are stateless (no config needed), so this registers plain
    instances rather than classes -- ``documents/parsers/__init__.py``
    calls this once per concrete parser at import time (the same
    explicit-import-over-filesystem-walk discovery pattern used for
    LLM providers and SQLAlchemy models, per final_review.md §1.3).
    """
    _PARSERS.append(parser)


def parser_for_file(file_path: Path) -> CVParser:
    """Return the first registered parser whose ``supports()`` is true.

    Args:
        file_path: The CV file to find a parser for.

    Returns:
        A registered ``CVParser`` instance.

    Raises:
        UnsupportedFormatError: No registered parser supports this file.
    """
    for parser in _PARSERS:
        if parser.supports(file_path):
            return parser
    raise UnsupportedFormatError(
        f"No registered CV parser supports '{file_path.suffix or '(no extension)'}'.",
        remedy="Convert the file to PDF, DOCX, or Markdown.",
    )
