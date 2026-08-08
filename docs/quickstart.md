# Quickstart

Status: Draft v1.0 · Last updated: 2026-08-08

Gets a clean clone to a passing `pytest` run and a working CLI. See
[`../README.md`](../README.md) for what the project is; this doc is
just the setup steps.

## 1. Prerequisites

- **Python 3.11+**.
- **A LaTeX distribution** providing `lualatex` and `pdftotext` on
  `PATH` — required for Resume Customization and Cover Letter
  rendering (`decisions.md` ADR-0007), not for anything else (setup,
  ranking, tracking, and the analytics dashboard need no LaTeX at
  all).
  - **Windows:** [MiKTeX](https://miktex.org/download). Confirmed
    working in this project's own dev environment; on first use,
    MiKTeX auto-installs missing packages (`enumitem`, `titlesec`,
    `hyperref`, etc.) the first time a template needs them — that
    first compile can take noticeably longer than the ~2s steady
    state, which is expected, not a hang (`progress_log.md`'s Phase
    11 entry). `pdftotext` ships with MiKTeX; if it's missing, install
    [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows)
    and add its `bin/` to `PATH`.
  - **macOS:** [MacTeX](https://tug.org/mactex/) (or the smaller
    [BasicTeX](https://tug.org/mactex/morepackages.html) plus
    `tlmgr install enumitem titlesec` etc.), and `brew install
    poppler` for `pdftotext`.
  - **Linux:** `texlive-latex-extra` (or your distro's equivalent) and
    `poppler-utils` from your package manager.
- An API key for at least one LLM provider (Anthropic, OpenAI, or a
  local Ollama install) — only needed once you run an agent that
  actually calls an LLM; `pytest` itself makes no live calls at all
  (`rules.md` §Testing Requirements).

## 2. Install

```bash
git clone https://github.com/sougataresearch/JOB_HUNT.git
cd JOB_HUNT
pip install -e ".[dev]"
```

This installs `jobhunt_core` in editable mode plus dev tooling (`ruff`,
`mypy`, `pytest`, `pre-commit`, `pip-audit`).

Optional but recommended if you'll be contributing changes:

```bash
pre-commit install
```

## 3. Configure

```bash
cp .env.example .env
```

Edit `.env` and set the API key for whichever provider
`config/llm.yaml` has as `default_provider` (Anthropic by default).
Never commit `.env` — it's gitignored (`rules.md` §Secrets Management).

## 4. Verify the install

```bash
pytest
```

Should pass with no live network/LLM calls made (every test uses a
fake or scripted provider, or a real local LaTeX compile — never a
real API call). Add `--cov-fail-under=80` to match the CI gate exactly
(`.github/workflows/ci.yml`).

## 5. Try it

```bash
# Parse a CV into a CandidateProfile
python -m cli.main setup path/to/your_cv.pdf

# See a ranked, paginated shortlist of scored postings (once some exist)
python -m cli.main rank --page 1

# Record an application status change
python -m cli.main outcome <job_posting_id> submitted

# Generate interview prep questions once status is interview_scheduled
python -m cli.main interview <job_posting_id> phone_screen

# Generate the offline HTML analytics dashboard
python -m cli.main report
```

Each command is also available as an equivalent Claude Code slash
command (`/setup`, `/rank`, `/outcome`, `/interview`, `/html-report`)
if you're driving the project through Claude Code rather than the
raw CLI (`.claude/commands/`, `decisions.md` ADR-0004 — the command
files are thin wrappers over the same CLI code, never a separate
implementation).

### What's not wired into a CLI/slash command yet

Job Search (`job_search` agent), Job Matching, ATS Optimization,
Resume Customization, Cover Letter, and Email Generation are all real,
tested, independently runnable agents (`Agent.run(input, ctx)`,
`api.md` §0) — `tests/e2e/test_full_apply_pipeline.py` chains all of
them together end to end against fixture data. They don't yet have
their own CLI/slash-command wrappers (no `/scrape` or `/apply`
command exists) — that orchestration layer is follow-on work, not
part of any phase's task breakdown so far (`tasks.md`); today, running
them means calling the agent directly in Python, the same way the E2E
test does. Cite this rather than assume a `/scrape`/`/apply` command
exists just because early architecture docs (`design.md`,
`architecture.md`) used those names illustratively.

## 6. Where to go next

- [`README.md`](../README.md) — project overview and doc index.
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — how to propose a change.
- [`../progress_log.md`](../progress_log.md) — the latest dated entry,
  with every currently-known open item and honest limitation.
