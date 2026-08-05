"""PDF CV parser (api.md §1 CV Parser API).

Uses ``pdfplumber`` for text extraction (decisions.md ADR-0001).
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from jobhunt_core.documents.parsers.sectioning import split_plaintext_sections
from jobhunt_core.schemas.document import ParsedDocument


class PDFParser:
    """Parses ``.pdf`` CV files."""

    def supports(self, file_path: Path) -> bool:
        """True for the ``.pdf`` extension."""
        return file_path.suffix.lower() == ".pdf"

    def parse(self, file_path: Path) -> ParsedDocument:
        """Extract text from every page and split into best-effort sections."""
        pages_text: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                pages_text.append(page.extract_text() or "")
        raw_text = "\n".join(pages_text)
        return ParsedDocument(
            raw_text=raw_text,
            sections=split_plaintext_sections(raw_text),
            source_format="pdf",
        )
