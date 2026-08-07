"""PDF text-extraction verification (decisions.md ADR-0007, tasks.md T11.2).

Compile alone doesn't prove a resume is ATS-parseable -- a PDF can
compile cleanly and still be unreadable to an ATS parser (e.g. content
rendered as an image, or a layout that garbles reading order). This
step closes that gap: extract the PDF's plain text via ``pdftotext``
and confirm every expected section header actually round-trips as
literal text.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from jobhunt_core.errors import RenderError
from jobhunt_core.schemas.document import PDFVerificationResult


def extract_pdf_text(
    pdf_path: Path,
    *,
    timeout_s: float = 30.0,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    """Extract ``pdf_path``'s plain text via ``pdftotext`` (layout-preserving, stdout).

    Raises:
        RenderError: ``pdftotext`` is missing, fails, or times out --
            never silently returns empty text as if it were a
            legitimate (if odd) extraction result.
    """
    try:
        result = run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except FileNotFoundError as exc:
        raise RenderError(
            "pdftotext is not installed or not on PATH.",
            remedy="Install a poppler-utils / MiKTeX distribution that provides pdftotext.",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RenderError(
            f"pdftotext extraction of '{pdf_path.name}' exceeded the {timeout_s}s timeout."
        ) from exc

    if result.returncode != 0:
        raise RenderError(
            f"pdftotext failed for '{pdf_path.name}' (exit code {result.returncode}).\n"
            f"{result.stderr}"
        )
    return result.stdout


def verify_pdf_text(
    pdf_path: Path,
    *,
    expected_headers: list[str],
    extracted_text_path: Path,
    timeout_s: float = 30.0,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> PDFVerificationResult:
    """Extract ``pdf_path``'s text, persist it, and confirm every expected header is present.

    Args:
        pdf_path: The compiled PDF to verify.
        expected_headers: Section headers that must appear verbatim in
            the extracted text (e.g. ``["Experience", "Education"]``).
        extracted_text_path: Where to write the extracted plaintext,
            for audit/debugging (``ResumeVersion.ats_extracted_text_path``).
        timeout_s: Per config.md §Timeouts.
        run: Injectable ``subprocess.run``-shaped callable for tests.

    Returns:
        A ``PDFVerificationResult`` -- ``passed`` is ``False`` (not an
        exception) when headers are missing, since that's an expected,
        actionable outcome the caller decides how to handle (e.g.
        retry rendering), not a hard failure like a missing binary.
    """
    text = extract_pdf_text(pdf_path, timeout_s=timeout_s, run=run)
    extracted_text_path.parent.mkdir(parents=True, exist_ok=True)
    extracted_text_path.write_text(text, encoding="utf-8")

    missing = [header for header in expected_headers if header not in text]
    return PDFVerificationResult(
        passed=not missing,
        missing_headers=missing,
        extracted_text=text,
        extracted_text_path=str(extracted_text_path),
    )
