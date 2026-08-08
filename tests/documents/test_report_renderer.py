"""Tests for the HTML report renderer (tasks.md T16.2, phases.md Phase 16).

No network calls anywhere in this module (Jinja2 string rendering
only) -- verifying "opens offline" is inherent to the implementation,
not something that needs mocking to prove.
"""

from pathlib import Path

from jobhunt_core.documents.report_renderer import render_report_html, write_report_html
from jobhunt_core.schemas.analytics import AnalyticsReport, RateBreakdown

_REPORT = AnalyticsReport(
    total_applications=7,
    total_submitted=6,
    insufficient_data=False,
    overall_response_rate=4 / 6,
    overall_interview_rate=2 / 6,
    overall_offer_rate=1 / 6,
    by_role_type=[
        RateBreakdown(
            key="Backend Engineer",
            total_submitted=4,
            response_rate=0.75,
            interview_rate=0.5,
            offer_rate=0.25,
        )
    ],
    by_source=[
        RateBreakdown(
            key="greenhouse",
            total_submitted=4,
            response_rate=0.5,
            interview_rate=0.0,
            offer_rate=0.0,
        )
    ],
)

_INSUFFICIENT_REPORT = AnalyticsReport(
    total_applications=2, total_submitted=2, insufficient_data=True
)


def test_render_report_html_includes_computed_rates_and_breakdowns() -> None:
    html = render_report_html(_REPORT)

    assert "7 total application" in html
    assert "6 submitted" in html
    assert "67%" in html  # overall_response_rate 4/6 rounded
    assert "Backend Engineer" in html
    assert "greenhouse" in html
    assert "<html" in html and "</html>" in html


def test_render_report_html_shows_caveat_when_insufficient_data() -> None:
    html = render_report_html(_INSUFFICIENT_REPORT)

    assert "Not enough data" in html
    # No rate stats block rendered when data is insufficient.
    assert "Response rate" not in html


def test_render_report_html_escapes_html_in_role_titles() -> None:
    """Job posting titles are not fully trusted content -- must be escaped, not injected raw."""
    report = AnalyticsReport(
        total_applications=5,
        total_submitted=5,
        insufficient_data=False,
        overall_response_rate=0.2,
        overall_interview_rate=0.0,
        overall_offer_rate=0.0,
        by_role_type=[
            RateBreakdown(
                key="<script>alert(1)</script>",
                total_submitted=5,
                response_rate=0.2,
                interview_rate=0.0,
                offer_rate=0.0,
            )
        ],
    )

    html = render_report_html(report)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_write_report_html_creates_parent_dirs_and_writes_file(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "report.html"

    result_path = write_report_html(_REPORT, output_path)

    assert result_path == output_path
    assert output_path.exists()
    assert "Backend Engineer" in output_path.read_text(encoding="utf-8")
