# Task Breakdown — JOB_HUNT

Status: Draft v1.0 · Last updated: 2026-08-02

Every phase in [`phases.md`](phases.md) is broken into tasks here.
Priority: **P0** blocking (nothing later works without it), **P1**
required for the phase's acceptance criteria, **P2** nice-to-have within
the phase (can slip to a follow-up task if time-boxed). Difficulty:
**S** (<2h), **M** (half a day), **L** (1–2 days).

## Phase 1 — Foundation

### T1.1 — Repo & packaging scaffold
- Priority: P0 · Dependencies: none · Difficulty: S
- Expected files: `pyproject.toml`, `src/jobhunt_core/__init__.py`,
  `.gitignore`, `.env.example`
- Completion checklist:
  - [ ] `pip install -e .` succeeds in a clean venv
  - [ ] Package importable as `import jobhunt_core`
  - [ ] `.gitignore` excludes `data/`, `.env`, `__pycache__/`, build artifacts

### T1.2 — Lint/type/format tooling
- Priority: P0 · Dependencies: T1.1 · Difficulty: S
- Expected files: `pyproject.toml` (`[tool.ruff]`, `[tool.mypy]`), `.pre-commit-config.yaml`
- Completion checklist:
  - [ ] `ruff check .` and `ruff format --check .` pass on empty skeleton
  - [ ] `mypy src/jobhunt_core` passes (strict) on empty skeleton
  - [ ] Pre-commit hook installed and verified locally

### T1.3 — CI pipeline skeleton
- Priority: P0 · Dependencies: T1.2 · Difficulty: S
- Expected files: `.github/workflows/ci.yml`
- Completion checklist:
  - [ ] CI runs lint, type-check, `pytest` (0 tests) on every PR
  - [ ] CI is green on a trivial docs-only PR

### T1.4 — Package tree skeleton per `folder_structure.md`
- Priority: P1 · Dependencies: T1.1 · Difficulty: S
- Expected files: `src/jobhunt_core/{agents,llm,storage,schemas,documents,sources,prompts,orchestration,config}/__init__.py`
- Completion checklist:
  - [ ] Every package has a one-line module docstring stating its
        responsibility (matches `architecture.md` §2 table)
  - [ ] No logic beyond docstrings/`__all__` stubs

### T1.5 — Logging config skeleton
- Priority: P1 · Dependencies: T1.1 · Difficulty: S
- Expected files: `src/jobhunt_core/logging_config.py`
- Completion checklist:
  - [ ] `configure_logging()` sets up stderr + rotating file handler per `design.md` §9
  - [ ] Unit test asserts no handler is attached twice on repeated calls

### T1.6 — License decision applied
- Priority: P2 · Dependencies: none · Difficulty: S
- Expected files: (none until Phase 18 — this task is "confirm the ADR-0009 decision stands," not "add LICENSE yet")
- Completion checklist:
  - [ ] Maintainer has explicitly confirmed MIT or an alternative before Phase 18

---

## Phase 2 — Configuration

### T2.1 — Settings loader
- Priority: P0 · Dependencies: T1.1 · Difficulty: M
- Expected files: `src/jobhunt_core/config/settings.py`, `config/llm.yaml`, `config/agents.yaml`, `config/sources.yaml`
- Completion checklist:
  - [ ] `Settings` (pydantic-settings) loads defaults → `local.yaml` → env vars, in that precedence
  - [ ] Missing required secret raises `ConfigError` with `.remedy`
  - [ ] Unit tests cover all three layers' override behavior

### T2.2 — `.env` secret handling
- Priority: P0 · Dependencies: T2.1 · Difficulty: S
- Expected files: `.env.example`, `src/jobhunt_core/config/secrets.py`
- Completion checklist:
  - [ ] `.env.example` lists every required key with a placeholder
  - [ ] Loading never logs the actual secret value

### T2.3 — Feature flags
- Priority: P1 · Dependencies: T2.1 · Difficulty: S
- Expected files: `config/agents.yaml` (`enabled: true/false` per agent)
- Completion checklist:
  - [ ] Disabling an agent in config makes the registry skip it at startup
  - [ ] Test: disabled agent is absent from `AgentRegistry.available()`

---

## Phase 3 — Core AI (LLM Provider Layer)

### T3.1 — `LLMProvider` protocol + schemas
- Priority: P0 · Dependencies: T2.1 · Difficulty: M
- Expected files: `src/jobhunt_core/llm/provider.py`, `src/jobhunt_core/llm/types.py`
- Completion checklist:
  - [ ] Protocol defines `complete()` and `complete_structured()`
  - [ ] Cost/token accounting fields defined on the response type

### T3.2 — Anthropic adapter
- Priority: P0 · Dependencies: T3.1 · Difficulty: M
- Expected files: `src/jobhunt_core/llm/providers/anthropic_provider.py`
- Completion checklist:
  - [ ] Implements the Protocol fully
  - [ ] Contract test suite passes using a recorded cassette (no live call in CI)

### T3.3 — OpenAI adapter
- Priority: P1 · Dependencies: T3.1 · Difficulty: M
- Expected files: `src/jobhunt_core/llm/providers/openai_provider.py`
- Completion checklist: same as T3.2, OpenAI-specific

### T3.4 — Local/Ollama adapter
- Priority: P2 · Dependencies: T3.1 · Difficulty: M
- Expected files: `src/jobhunt_core/llm/providers/ollama_provider.py`
- Completion checklist: same contract-test pattern; documented as
  best-effort (local models may not support structured output as
  reliably — noted, not blocking)

### T3.5 — Retry/backoff policy
- Priority: P0 · Dependencies: T3.1 · Difficulty: S
- Expected files: `src/jobhunt_core/llm/retry.py`
- Completion checklist:
  - [ ] Exponential backoff + jitter, max 3 attempts, retryable-error allowlist only
  - [ ] Unit tests simulate 429/5xx/timeout/4xx and assert correct retry/no-retry behavior

---

## Phase 4 — Storage & Schemas

### T4.1 — Core Pydantic schemas
- Priority: P0 · Dependencies: T1.1 · Difficulty: M
- Expected files: `src/jobhunt_core/schemas/{profile,job,match,ats,application,interview}.py`
- Completion checklist:
  - [ ] Every schema in `database.md` §Entities has a corresponding Pydantic model
  - [ ] `schemas/` has zero imports from any other `jobhunt_core` subpackage

### T4.2 — SQLAlchemy models
- Priority: P0 · Dependencies: T4.1 · Difficulty: M
- Expected files: `src/jobhunt_core/storage/models/*.py`
- Completion checklist:
  - [ ] One model per `database.md` table, field-for-field match
  - [ ] Constraints (unique, FK) match `database.md` exactly

### T4.3 — Alembic setup + initial migration
- Priority: P0 · Dependencies: T4.2 · Difficulty: S
- Expected files: `migrations/env.py`, `migrations/versions/0001_initial.py`
- Completion checklist:
  - [ ] `alembic upgrade head` and `alembic downgrade base` both succeed on a scratch DB

### T4.4 — Repositories
- Priority: P0 · Dependencies: T4.2 · Difficulty: M
- Expected files: `src/jobhunt_core/storage/repositories/*.py`
- Completion checklist:
  - [ ] One repository per aggregate (Profile, Job, Match, ATS, Application, Interview)
  - [ ] Round-trip test (write → read) passes for every repository

---

## Phase 5 — CV Analysis (Resume Analysis Agent)

### T5.1 — CV file parsers
- Priority: P0 · Dependencies: T1.1 · Difficulty: M
- Expected files: `src/jobhunt_core/documents/parsers/{pdf,docx,markdown}.py`
- Completion checklist:
  - [ ] Each parser extracts raw text + basic structure (sections) from its format
  - [ ] Tested against 3+ fixture CVs per format

### T5.2 — Resume Analysis Agent + prompt
- Priority: P0 · Dependencies: T3.2, T4.1, T5.1 · Difficulty: L
- Expected files: `src/jobhunt_core/agents/resume_analysis_agent.py`, `prompts/library/resume_analysis/extract_profile.md`
- Completion checklist:
  - [ ] Produces a valid `CandidateProfile` from each fixture CV
  - [ ] Sparse/ambiguous input yields explicit "not found," never a guess presented as fact
  - [ ] Golden-file test passes within agreed tolerance

### T5.3 — Onboarding command
- Priority: P1 · Dependencies: T5.2 · Difficulty: S
- Expected files: `.claude/commands/setup.md`, `cli/commands/setup.py`
- Completion checklist:
  - [ ] Running `/setup` (or `jobhunt setup`) end-to-end produces a persisted `CandidateProfile`

---

## Phase 6 — Skill Gap Analysis

### T6.1 — Skill Gap Agent + prompt
- Priority: P1 · Dependencies: T5.2 · Difficulty: M
- Expected files: `src/jobhunt_core/agents/skill_gap_agent.py`, `src/jobhunt_core/schemas/skill_gap.py`, `prompts/library/skill_gap/analyze.md`
- Completion checklist:
  - [ ] Every gap in output cites profile evidence or explicit absence
  - [ ] Golden-file test passes

---

## Phase 7 — Job Search

### T7.1 — Source connector interface
- Priority: P0 · Dependencies: T4.1 · Difficulty: S
- Expected files: `src/jobhunt_core/sources/base.py`
- Completion checklist:
  - [ ] `@register_source` decorator + `JobSource` Protocol defined

### T7.2 — First API-based connector
- Priority: P0 · Dependencies: T7.1 · Difficulty: M
- Expected files: `src/jobhunt_core/sources/<provider>_source.py`
- Completion checklist:
  - [ ] Confirmed ToS-compliant per `rules.md` before implementation
  - [ ] Returns normalized `JobPosting` objects

### T7.3 — Manual paste/import connector
- Priority: P1 · Dependencies: T7.1 · Difficulty: S
- Expected files: `src/jobhunt_core/sources/manual_import_source.py`
- Completion checklist:
  - [ ] Accepts a pasted URL/text or file and normalizes to `JobPosting`

### T7.4 — Job Search Agent + dedup
- Priority: P0 · Dependencies: T7.2, T7.3, T4.4 · Difficulty: M
- Expected files: `src/jobhunt_core/agents/job_search_agent.py`
- Completion checklist:
  - [ ] Dedup key = normalized (company, title, location) + content hash
  - [ ] Circuit breaker: N consecutive source failures → skip source, continue batch
  - [ ] Test: overlapping re-run produces no duplicate rows

---

## Phase 8 — Job Matching

### T8.1 — Job Matching Agent + prompt
- Priority: P0 · Dependencies: T5.2, T7.4 · Difficulty: L
- Expected files: `src/jobhunt_core/agents/job_matching_agent.py`, `prompts/library/job_matching/score.md`
- Completion checklist:
  - [ ] Score reproducible at temperature=0 on fixed inputs
  - [ ] Rationale cites concrete posting/profile text
  - [ ] Regression suite (~10 labeled pairs) within tolerance

---

## Phase 9 — Ranking

### T9.1 — Ranking function + command
- Priority: P1 · Dependencies: T8.1 · Difficulty: S
- Expected files: `src/jobhunt_core/orchestration/ranking.py`, `.claude/commands/rank.md`, `cli/commands/rank.py`
- Completion checklist:
  - [ ] Stable sort; same inputs → same order
  - [ ] Paginated output (progressive disclosure per `design.md` §2)

---

## Phase 10 — ATS Optimization

### T10.1 — ATS Optimization Agent + prompt
- Priority: P1 · Dependencies: T5.2, T7.4 · Difficulty: M
- Expected files: `src/jobhunt_core/agents/ats_optimization_agent.py`, `src/jobhunt_core/schemas/ats.py`, `prompts/library/ats/analyze.md`
- Completion checklist:
  - [ ] Distinguishes "supported by real experience" vs. "unsupported, do not add" gaps
  - [ ] Fixture-tested against known keyword-gap cases

---

## Phase 11 — Resume Customization

### T11.1 — `DocumentRenderer` interface + Jinja2/LaTeX pipeline
- Priority: P0 · Dependencies: T4.4 · Difficulty: L
- Expected files: `src/jobhunt_core/documents/renderer.py`, `documents/templates/cv/*.tex.jinja`
- Completion checklist:
  - [ ] Jinja2 escaping verified against LaTeX special characters (fixture with `&`, `%`, `_`, `#`)
  - [ ] Compiles cleanly with lualatex/xelatex on a clean install

### T11.2 — PDF verification step
- Priority: P0 · Dependencies: T11.1 · Difficulty: M
- Expected files: `src/jobhunt_core/documents/verify.py`
- Completion checklist:
  - [ ] `pdftotext` extraction confirms expected section headers present
  - [ ] Failure surfaces the actual LaTeX log to the user, no silent fallback

### T11.3 — Resume Customization Agent (drafter→reviewer loop)
- Priority: P0 · Dependencies: T10.1, T11.1, T11.2 · Difficulty: L
- Expected files: `src/jobhunt_core/agents/resume_customization_agent.py`, `prompts/library/resume_customization/{draft,review}.md`
- Completion checklist:
  - [ ] Reviewer pass runs on fresh context, not the drafter's own conversation
  - [ ] No fabricated content in output (AI Coding Rule 1) verified by fixture test

---

## Phase 12 — Cover Letters

### T12.1 — Cover letter template
- Priority: P1 · Dependencies: T11.1 · Difficulty: S
- Expected files: `documents/templates/cover_letter/*.tex.jinja`

### T12.2 — Cover Letter Agent + prompt
- Priority: P1 · Dependencies: T11.3, T12.1 · Difficulty: M
- Expected files: `src/jobhunt_core/agents/cover_letter_agent.py`, `prompts/library/cover_letter/draft.md`
- Completion checklist:
  - [ ] References ≥N concrete posting details (keyword-presence eval)
  - [ ] No contradiction with tailored resume content (cross-check test)

---

## Phase 13 — Email Automation

### T13.1 — Email Generation Agent + prompt
- Priority: P1 · Dependencies: T12.2 · Difficulty: S
- Expected files: `src/jobhunt_core/agents/email_agent.py`, `src/jobhunt_core/schemas/email.py`, `prompts/library/email/draft.md`
- Completion checklist:
  - [ ] Draft correctly references generated attachment paths
  - [ ] Output explicitly flagged as unsent draft requiring user action

---

## Phase 14 — Application Tracking

### T14.1 — Application/Event tables + repo (if not already scaffolded in Phase 4)
- Priority: P0 · Dependencies: T4.4 · Difficulty: S
- Expected files: `src/jobhunt_core/storage/models/application.py`, `src/jobhunt_core/storage/repositories/application_repo.py`

### T14.2 — Application Tracking Agent + status API
- Priority: P0 · Dependencies: T14.1 · Difficulty: M
- Expected files: `src/jobhunt_core/agents/application_tracking_agent.py`
- Completion checklist:
  - [ ] Every status transition appends an `ApplicationEvent` row (never overwrites history)
  - [ ] CSV export matches hand-computed fixture aggregates

### T14.3 — `/outcome` command
- Priority: P1 · Dependencies: T14.2 · Difficulty: S
- Expected files: `.claude/commands/outcome.md`, `cli/commands/outcome.py`

---

## Phase 15 — Interview Preparation

### T15.1 — Interview Prep Agent + prompt
- Priority: P1 · Dependencies: T8.1, T11.3, T14.2 · Difficulty: M
- Expected files: `src/jobhunt_core/agents/interview_prep_agent.py`, `src/jobhunt_core/schemas/interview.py`, `prompts/library/interview/prepare.md`
- Completion checklist:
  - [ ] Talking points traceable to specific resume bullets/posting lines
  - [ ] Triggered automatically (or on command) when status → `interview_scheduled`

---

## Phase 16 — Career Analytics

### T16.1 — Career Analytics Agent
- Priority: P2 · Dependencies: T14.2 · Difficulty: M
- Expected files: `src/jobhunt_core/agents/career_analytics_agent.py`, `src/jobhunt_core/schemas/analytics.py`
- Completion checklist:
  - [ ] Response/interview/offer rate computations match hand-verified fixture numbers

### T16.2 — HTML dashboard generator
- Priority: P2 · Dependencies: T16.1 · Difficulty: M
- Expected files: `src/jobhunt_core/documents/report_renderer.py`, `.claude/commands/html-report.md`
- Completion checklist:
  - [ ] Generated HTML opens offline, zero network calls, matches underlying CSV data

---

## Phase 17 — Testing & Quality Hardening

### T17.1 — End-to-end pipeline fixture test
- Priority: P0 · Dependencies: all prior phases · Difficulty: L
- Expected files: `tests/e2e/test_full_apply_pipeline.py`
- Completion checklist:
  - [ ] Fixture CV + fixture posting → full package generated, no live network/LLM calls

### T17.2 — Coverage & security CI gates
- Priority: P0 · Dependencies: T17.1 · Difficulty: S
- Expected files: `.github/workflows/ci.yml` (updated)
- Completion checklist:
  - [ ] Coverage gate ≥80% on `src/jobhunt_core` non-agent-prompt logic
  - [ ] `pip-audit`/secret-scan wired in and passing

---

## Phase 18 — Deployment & Open-Source Release

### T18.1 — Public README + quickstart
- Priority: P0 · Dependencies: T17.2 · Difficulty: M
- Expected files: `README.md` (expanded), `docs/quickstart.md`

### T18.2 — Contribution scaffolding
- Priority: P1 · Dependencies: T18.1 · Difficulty: S
- Expected files: `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE.md`

### T18.3 — License + first release
- Priority: P0 · Dependencies: T18.1 · Difficulty: S
- Expected files: `LICENSE`
- Completion checklist:
  - [ ] License confirmed with maintainer (`decisions.md` ADR-0009)
  - [ ] Tagged release pushed to `https://github.com/sougataresearch/JOB_HUNT`
        **only after explicit maintainer go-ahead** — pushing to a
        public remote is a one-way, visible action (see this
        assistant's own operating rules on confirming before shared-state
        actions)
