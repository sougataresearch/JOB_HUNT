"""Markdown CV parser (api.md §1 CV Parser API)."""

from __future__ import annotations

from pathlib import Path

from jobhunt_core.documents.parsers.sectioning import split_markdown_sections
from jobhunt_core.schemas.document import ParsedDocument


class MarkdownParser:
    """Parses ``.md``/``.markdown`` CV files."""

    def supports(self, file_path: Path) -> bool:
        """True for ``.md``/``.markdown`` extensions."""
        return file_path.suffix.lower() in {".md", ".markdown"}

    def parse(self, file_path: Path) -> ParsedDocument:
        """Read the file and split it into sections by Markdown heading."""
        raw_text = file_path.read_text(encoding="utf-8")
        return ParsedDocument(
            raw_text=raw_text,
            sections=split_markdown_sections(raw_text),
            source_format="markdown",
        )
