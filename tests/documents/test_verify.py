"""Tests for the PDF text-extraction verification step (tasks.md T11.2).

Real ``pdftotext`` calls against a real compiled PDF (this dev
environment has it installed and verified working) -- same rationale
as tests/documents/test_renderer.py for not mocking a local, offline
binary.
"""

import subprocess
from pathlib import Path

import pytest

from jobhunt_core.documents.renderer import LaTeXRenderer
from jobhunt_core.documents.verify import extract_pdf_text, verify_pdf_text
from jobhunt_core.errors import RenderError


@pytest.fixture
def compiled_pdf(tmp_path: Path) -> Path:
    """A real, compiled PDF with known section headers, for extraction tests."""
    renderer = LaTeXRenderer()
    template = r"""\documentclass{article}
\begin{document}
\section*{Experience}
Backend Engineer at Acme.
\section*{Education}
State University.
\end{document}
"""
    tex = renderer.render(template, {})
    return renderer.compile(tex, tmp_path, base_name="doc")


def test_extract_pdf_text_returns_real_content(compiled_pdf: Path) -> None:
    """pdftotext extracts the PDF's actual text content."""
    text = extract_pdf_text(compiled_pdf)

    assert "Experience" in text
    assert "Education" in text
    assert "Backend Engineer" in text


def test_extract_pdf_text_missing_binary_raises_render_error(tmp_path: Path) -> None:
    """A missing pdftotext binary surfaces a clear, actionable RenderError."""

    def _not_found(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("pdftotext not found")

    with pytest.raises(RenderError) as exc_info:
        extract_pdf_text(tmp_path / "doc.pdf", run=_not_found)

    assert exc_info.value.remedy


def test_extract_pdf_text_timeout_raises_render_error(tmp_path: Path) -> None:
    """An extraction exceeding the timeout ceiling raises RenderError."""

    def _always_times_out(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="pdftotext", timeout=0.01)

    with pytest.raises(RenderError, match="timeout"):
        extract_pdf_text(tmp_path / "doc.pdf", timeout_s=0.01, run=_always_times_out)


def test_verify_pdf_text_passes_when_all_headers_present(
    compiled_pdf: Path, tmp_path: Path
) -> None:
    """All expected headers found -> passed=True, no missing headers."""
    result = verify_pdf_text(
        compiled_pdf,
        expected_headers=["Experience", "Education"],
        extracted_text_path=tmp_path / "extracted.txt",
    )

    assert result.passed is True
    assert result.missing_headers == []
    assert "Experience" in result.extracted_text


def test_verify_pdf_text_fails_when_a_header_is_missing(compiled_pdf: Path, tmp_path: Path) -> None:
    """A header the PDF doesn't contain -> passed=False, named in missing_headers."""
    result = verify_pdf_text(
        compiled_pdf,
        expected_headers=["Experience", "Certifications"],
        extracted_text_path=tmp_path / "extracted.txt",
    )

    assert result.passed is False
    assert result.missing_headers == ["Certifications"]


def test_verify_pdf_text_persists_extracted_text(compiled_pdf: Path, tmp_path: Path) -> None:
    """The extracted plaintext is written to extracted_text_path for audit/debugging."""
    extracted_path = tmp_path / "extracted.txt"

    result = verify_pdf_text(compiled_pdf, expected_headers=[], extracted_text_path=extracted_path)

    assert extracted_path.exists()
    assert extracted_path.read_text(encoding="utf-8") == result.extracted_text
    assert result.extracted_text_path == str(extracted_path)
