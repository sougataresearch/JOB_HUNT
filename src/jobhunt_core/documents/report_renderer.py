"""Static HTML dashboard generator for ``AnalyticsReport`` (design.md §1, tasks.md T16.2).

Deliberately not built on the ``DocumentRenderer`` Protocol
(``documents/renderer.py``) -- that Protocol's ``compile()`` step
shells out to a LaTeX engine, a contract report rendering has no use
for (rules.md no-speculative-abstraction: don't force an unrelated
concern into an existing interface just because it also produces a
file). This is a standalone Jinja2 render with no compile step and no
external resources -- self-contained, offline, zero network calls
(tasks.md T16.2 checklist: "opens offline, zero network calls").
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

from jobhunt_core.schemas.analytics import AnalyticsReport

_TEMPLATE_SOURCE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>JOB_HUNT Career Analytics</title>
<style>
  body { font-family: system-ui, -apple-system, sans-serif; max-width: 900px;
         margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
  h1 { font-size: 1.5rem; }
  h2 { font-size: 1.1rem; margin-top: 2rem; }
  table { border-collapse: collapse; width: 100%; margin: 0.5rem 0 1.5rem; }
  th, td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #ddd; }
  .stats { display: flex; gap: 2rem; margin: 1rem 0; }
  .stat .value { font-size: 1.8rem; font-weight: 600; }
  .stat .label { color: #555; font-size: 0.9rem; }
  .caveat { background: #fff4e5; border: 1px solid #f0c36d; padding: 0.75rem 1rem;
            border-radius: 4px; }
</style>
</head>
<body>
<h1>JOB_HUNT Career Analytics</h1>
<p>{{ report.total_applications }} total application(s), {{ report.total_submitted }} submitted.</p>
{% if report.insufficient_data %}
<p class="caveat">Not enough data yet (fewer than 5 submitted applications) --
rates withheld rather than shown as if they meant something.</p>
{% else %}
<div class="stats">
  <div class="stat">
    <div class="value">{{ "%.0f"|format(report.overall_response_rate * 100) }}%</div>
    <div class="label">Response rate</div>
  </div>
  <div class="stat">
    <div class="value">{{ "%.0f"|format(report.overall_interview_rate * 100) }}%</div>
    <div class="label">Interview rate</div>
  </div>
  <div class="stat">
    <div class="value">{{ "%.0f"|format(report.overall_offer_rate * 100) }}%</div>
    <div class="label">Offer rate</div>
  </div>
</div>

<h2>By role</h2>
<table>
<tr><th>Role</th><th>Submitted</th><th>Response</th><th>Interview</th><th>Offer</th></tr>
{% for row in report.by_role_type %}
<tr>
  <td>{{ row.key }}</td>
  <td>{{ row.total_submitted }}</td>
  <td>{{ "%.0f"|format(row.response_rate * 100) }}%</td>
  <td>{{ "%.0f"|format(row.interview_rate * 100) }}%</td>
  <td>{{ "%.0f"|format(row.offer_rate * 100) }}%</td>
</tr>
{% endfor %}
</table>

<h2>By source</h2>
<table>
<tr><th>Source</th><th>Submitted</th><th>Response</th><th>Interview</th><th>Offer</th></tr>
{% for row in report.by_source %}
<tr>
  <td>{{ row.key }}</td>
  <td>{{ row.total_submitted }}</td>
  <td>{{ "%.0f"|format(row.response_rate * 100) }}%</td>
  <td>{{ "%.0f"|format(row.interview_rate * 100) }}%</td>
  <td>{{ "%.0f"|format(row.offer_rate * 100) }}%</td>
</tr>
{% endfor %}
</table>
{% endif %}
</body>
</html>
"""

# autoescape=True (unlike prompts/loader.py's plain-text prompt
# environment): role titles/source names ultimately originate from
# sourced job posting content, so escape them going into HTML even
# though they're not going to an LLM here.
_env = Environment(autoescape=True)
_template = _env.from_string(_TEMPLATE_SOURCE)


def render_report_html(report: AnalyticsReport) -> str:
    """Render an ``AnalyticsReport`` as a self-contained, offline HTML page."""
    return _template.render(report=report)


def write_report_html(report: AnalyticsReport, output_path: Path) -> Path:
    """Render ``report`` and write it to ``output_path``, creating parent dirs as needed.

    Args:
        report: The report to render.
        output_path: Where to write the HTML file.

    Returns:
        ``output_path``, for convenient chaining.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report_html(report), encoding="utf-8")
    return output_path
