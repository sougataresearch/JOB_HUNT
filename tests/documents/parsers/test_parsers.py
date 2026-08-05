"""Tests for CV parsers (tasks.md T5.1).

Parametrized across the 3 fixture personas x 3 formats (9 fixture
files, tests/fixtures/cvs/), per T5.1's "tested against 3+ fixture
CVs per format" checklist.
"""

from pathlib import Path

import pytest

from jobhunt_core.documents.parsers import parser_for_file
from jobhunt_core.documents.parsers.docx import DOCXParser
from jobhunt_core.documents.parsers.markdown import MarkdownParser
from jobhunt_core.documents.parsers.pdf import PDFParser
from jobhunt_core.errors import UnsupportedFormatError

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "cvs"
PERSONAS = ("jane_doe_complete", "sparse_partial", "alex_kim_standard")
FORMATS = ("md", "docx", "pdf")


@pytest.mark.parametrize("persona", PERSONAS)
@pytest.mark.parametrize("ext", FORMATS)
def test_parser_extracts_nonempty_raw_text(persona: str, ext: str) -> None:
    """Every fixture, in every format, yields non-empty raw_text."""
    file_path = FIXTURES_DIR / f"{persona}.{ext}"
    parser = parser_for_file(file_path)

    parsed = parser.parse(file_path)

    assert parsed.raw_text.strip()


@pytest.mark.parametrize("persona", PERSONAS)
@pytest.mark.parametrize("ext", FORMATS)
def test_parser_finds_experience_section(persona: str, ext: str) -> None:
    """Every persona/format extracts an 'Experience' section (all 3 have one)."""
    file_path = FIXTURES_DIR / f"{persona}.{ext}"
    parser = parser_for_file(file_path)

    parsed = parser.parse(file_path)

    assert "Experience" in parsed.sections
    assert parsed.sections["Experience"].strip()


def test_markdown_parser_supports_md_and_markdown_extensions() -> None:
    """MarkdownParser recognizes both .md and .markdown."""
    parser = MarkdownParser()

    assert parser.supports(Path("cv.md"))
    assert parser.supports(Path("cv.markdown"))
    assert not parser.supports(Path("cv.pdf"))


def test_pdf_parser_supports_only_pdf() -> None:
    """PDFParser recognizes only .pdf."""
    parser = PDFParser()

    assert parser.supports(Path("cv.pdf"))
    assert not parser.supports(Path("cv.docx"))


def test_docx_parser_supports_only_docx() -> None:
    """DOCXParser recognizes only .docx."""
    parser = DOCXParser()

    assert parser.supports(Path("cv.docx"))
    assert not parser.supports(Path("cv.pdf"))


def test_parser_for_file_raises_on_unsupported_extension() -> None:
    """An unrecognized extension raises UnsupportedFormatError with a remedy."""
    with pytest.raises(UnsupportedFormatError) as exc_info:
        parser_for_file(Path("resume.exe"))

    assert exc_info.value.remedy


def test_sparse_cv_has_no_education_or_skills_sections() -> None:
    """The deliberately sparse fixture has no Education/Skills sections at all.

    This is a parser-level precondition for the agent-level "explicit
    not found, never guessed" acceptance criterion (phases.md Phase 5)
    -- if the parser can't find these sections, the agent has no basis
    to invent them.
    """
    file_path = FIXTURES_DIR / "sparse_partial.md"
    parser = parser_for_file(file_path)

    parsed = parser.parse(file_path)

    assert "Education" not in parsed.sections
    assert "Skills" not in parsed.sections
