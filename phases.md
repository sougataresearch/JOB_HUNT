# Development Phases — JOB_HUNT

Status: Draft v1.0 · Last updated: 2026-08-02 · Progress last marked: 2026-08-08

**Phases 1–16 of 18 are complete** (✅ below); 17–18 (⬜) are not yet
started. Each phase's `**Status:**` line is a pointer, not the record
of truth — see `progress_log.md` for the detailed, dated build history
behind each completed phase, and `memory.md` for a current-state
snapshot.

This is the **authoritative phase roadmap and scope boundary list**. Do
not implement beyond the phase actually being worked on
(`sougata_solver`-style convention, applied here too — see this repo's
`rules.md`). Each phase lists Objectives, Deliverables, Dependencies,
Acceptance Criteria, and Estimated Complexity (S / M / L / XL, roughly
1–2 / 3–5 / 1–2 weeks / 2–4 weeks of solo part-time effort). Exact task
breakdowns per phase live in [`tasks.md`](tasks.md); build sequencing
with fine-grained dependencies lives in
[`implementation_order.md`](implementation_order.md).

---

## Phase 1 — Foundation

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Stand up the repository skeleton so every later phase
has somewhere correct to put its code.

**Deliverables:**
- `pyproject.toml` (`src/` layout, package name `jobhunt_core`), `ruff`,
  `mypy`, `pytest` configured.
- Pre-commit hooks (lint, format, type-check) per `rules.md`.
- CI skeleton (lint + type-check + empty test run) per `rules.md`
  §Git Workflow.
- `folder_structure.md`-conformant empty package tree with `__init__.py`
  stubs and module-level docstrings only (no logic).
- Logging config (`design.md` §9) wired to a no-op default.
- `.gitignore`, `.env.example`, `LICENSE` decision applied
  (`decisions.md` ADR-0009).

**Dependencies:** None (first phase).

**Acceptance Criteria:** `pip install -e .` succeeds; `pytest` runs
(0 tests, exit 0); `ruff check` and `mypy` pass on the empty skeleton;
CI is green on a trivial PR.

**Estimated Complexity:** S

---

## Phase 2 — Configuration

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Establish the single, validated source of truth for all
settings before any module that needs config is built.

**Deliverables:** `config/` YAML defaults (`llm.yaml`, `agents.yaml`,
`sources.yaml`), `pydantic-settings`-based `Settings` loader with the
layering in `design.md` §8, `.env` secret loading, `config.md`-specified
feature flags.

**Dependencies:** Phase 1.

**Acceptance Criteria:** Loading config with a missing required secret
raises a clear `JobHuntError` with a `.remedy` string (`design.md` §10);
unit tests cover default → local override → env-var precedence.

**Estimated Complexity:** S

---

## Phase 3 — Core AI (LLM Provider Layer)

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Build the provider-agnostic LLM access layer every agent
will depend on (`decisions.md` ADR-0003).

**Deliverables:** `LLMProvider` Protocol, Anthropic/OpenAI/Ollama
adapters, retry/backoff policy (`design.md` §11), structured-output
support (Pydantic-typed completions), cost/token accounting hook for
logging (`design.md` §9).

**Dependencies:** Phase 2 (needs provider config).

**Acceptance Criteria:** A fake/recorded provider adapter passes the
same contract test suite as the real adapters (`testing.md`); retry
policy unit-tested against simulated 429/5xx/timeout responses without
live network calls.

**Estimated Complexity:** M

---

## Phase 4 — Storage & Schemas

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Define the shared data vocabulary (`schemas/`) and
persistence layer (`storage/`) that every agent reads/writes through.

**Deliverables:** Pydantic schemas for `CandidateProfile`, `JobPosting`,
`MatchScore`, `ATSReport`, `Application`, `ApplicationEvent`,
`InterviewPrepPack` (full detail in `database.md`); SQLAlchemy models +
Alembic initial migration; repository classes (`ProfileRepo`, `JobRepo`,
`ApplicationRepo`, etc.).

**Dependencies:** Phase 1.

**Acceptance Criteria:** Round-trip test (write a row via repository,
read it back, fields match) passes for every model; Alembic
`upgrade`/`downgrade` both succeed on a scratch DB.

**Estimated Complexity:** M

---

## Phase 5 — CV Analysis (Resume Analysis Agent)

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Turn a raw CV file into a structured `CandidateProfile`.

**Deliverables:** PDF/DOCX/Markdown parsers (`documents/parsers/`),
Resume Analysis Agent + prompt (`prompts.md`), `.claude/commands/setup.md`
or equivalent onboarding command.

**Dependencies:** Phases 3, 4.

**Acceptance Criteria:** Given 3 sample CVs (varied formats, fixtures
under `tests/fixtures/`), the agent extracts skills/experience/education
matching a hand-verified golden output within an agreed tolerance
(`testing.md` §AI Evaluation); no fabricated fields when input is
sparse (returns explicit "not found," never invents).

**Estimated Complexity:** M

---

## Phase 6 — Skill Gap Analysis (Skill Gap Agent)

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Compare a `CandidateProfile` against a target role/
market to identify missing or weak skills.

**Deliverables:** Skill Gap Agent + prompt, `SkillGapReport` schema.

**Dependencies:** Phase 5.

**Acceptance Criteria:** Report lists gaps with rationale tied to
specific profile evidence (or explicit absence thereof), not generic
advice; golden-file tests pass.

**Estimated Complexity:** S

---

## Phase 7 — Job Search (Job Search Agent + Source Connectors)

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Source job postings from multiple channels with
deduplication.

**Deliverables:** `sources/` connector interface + at least 2 concrete
connectors (one API-based, one manual-paste/import-based, per
`PRD.md` §9 ToS constraint), Job Search Agent, dedup logic keyed on
normalized (company, title, location) + content hash.

**Dependencies:** Phases 3, 4.

**Acceptance Criteria:** Running search twice with overlapping results
produces no duplicate `JobPosting` rows; a failing source does not abort
the batch (`design.md` §10 per-item isolation); circuit breaker verified
with a simulated always-failing source.

**Estimated Complexity:** M

---

## Phase 8 — Job Matching (Job Matching Agent)

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Score compatibility between a `CandidateProfile` and a
`JobPosting`, with rationale.

**Deliverables:** Job Matching Agent + prompt, `MatchScore` schema
including matched/missing requirements and any red flags.

**Dependencies:** Phases 5, 7.

**Acceptance Criteria:** Score is reproducible given fixed inputs +
model + temperature=0 (`PRD.md` §6 Determinism); rationale references
concrete posting/profile text, not generic filler; regression suite of
~10 labeled (profile, posting, expected-score-band) pairs stays within
tolerance across prompt changes (`testing.md`).

**Estimated Complexity:** M

---

## Phase 9 — Ranking

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Turn a batch of `MatchScore`s into a prioritized,
human-reviewable shortlist.

**Deliverables:** Ranking function/agent (may be a mode of Job Matching
Agent rather than a fully separate agent — decide during
implementation and record as an ADR if it changes the plan), `/rank`
Claude Code command, CLI `jobhunt rank`.

**Dependencies:** Phase 8.

**Acceptance Criteria:** Given N scored postings, output is sorted,
paginated for progressive disclosure (`design.md` §2), and stable
(same inputs → same order).

**Estimated Complexity:** S

---

## Phase 10 — ATS Optimization (ATS Optimization Agent)

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Identify keyword/formatting gaps between a
`CandidateProfile`/CV draft and a `JobPosting` that would hurt automated
parsing.

**Deliverables:** ATS Optimization Agent + prompt, `ATSReport` schema,
integration point ahead of Resume Customization Agent.

**Dependencies:** Phases 5, 7.

**Acceptance Criteria:** Report distinguishes "missing keyword present
in your real experience — add it" from "missing keyword NOT supported
by your experience — do not fabricate it" (`rules.md` never-invent
rule); tested against fixtures with known gaps.

**Estimated Complexity:** S/M

---

## Phase 11 — Resume Customization (Resume Customization Agent + LaTeX Rendering)

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Produce a tailored, compiled, ATS-verified CV PDF for a
specific posting.

**Deliverables:** Resume Customization Agent, LaTeX template(s)
(`documents/templates/`), `DocumentRenderer` (`decisions.md` ADR-0007),
drafter→reviewer verification loop, PDF-text-extraction verification
step.

**Dependencies:** Phases 4, 8, 10.

**Acceptance Criteria:** Given a profile + posting + ATS report, output
PDF compiles without manual intervention on a clean LaTeX install;
extracted PDF text contains all expected section headers and no
fabricated content; a deliberately malformed LaTeX special character in
input CV content does not break compilation (escaping tested).

**Estimated Complexity:** L

---

## Phase 12 — Cover Letters (Cover Letter Agent)

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Generate a tailored cover letter referencing the
specific posting and the tailored resume.

**Deliverables:** Cover Letter Agent + prompt, cover-letter LaTeX
template, reuse of the Phase 11 rendering/verification pipeline.

**Dependencies:** Phase 11.

**Acceptance Criteria:** Letter references at least N concrete details
from the posting (checked via a simple keyword-presence eval, not just
vibes — `testing.md`); no content contradicts the tailored resume.

**Estimated Complexity:** M

---

## Phase 13 — Email Automation (Email Generation Agent)

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Draft the application submission email.

**Deliverables:** Email Generation Agent + prompt, `DraftEmail` schema,
review-gate integration (never auto-sent — `PRD.md` §9).

**Dependencies:** Phase 12.

**Acceptance Criteria:** Draft includes correct attachments referenced
(tailored CV + cover letter file paths), correct recipient placeholder
handling, and is flagged clearly as a draft requiring explicit send
action.

**Estimated Complexity:** S

---

## Phase 14 — Application Tracking (Application Tracking Agent)

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Persist and manage the lifecycle of every application.

**Deliverables:** Application Tracking Agent, `Application` /
`ApplicationEvent` tables (`database.md`), CSV export, status-transition
API, `.claude/commands/outcome.md`-equivalent command.

**Dependencies:** Phase 4 (and conceptually consumes output of Phases
11–13, but can be built/tested with synthetic data before those land —
see `implementation_order.md` for why tracking is sequenced where it
is).

**Acceptance Criteria:** Every status transition creates an
`ApplicationEvent` row (`design.md` §3); CSV export reproduces a report
matching hand-computed aggregates on fixture data.

**Estimated Complexity:** M

---

## Phase 15 — Interview Preparation (Interview Prep Agent)

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Generate likely interview questions and talking points
once an application reaches "interview scheduled."

**Deliverables:** Interview Prep Agent + prompt, `InterviewPrepPack`
schema, `/interview` command trigger on status change.

**Dependencies:** Phases 8, 11, 14.

**Acceptance Criteria:** Talking points are grounded in the tailored
resume and posting (traceable back to specific bullet points), not
generic interview advice; golden-file tests pass.

**Estimated Complexity:** M

---

## Phase 16 — Career Analytics (Career Analytics Agent)

**Status:** ✅ Complete — see `progress_log.md`.

**Objectives:** Aggregate application history into actionable trends.

**Deliverables:** Career Analytics Agent, `AnalyticsReport` schema,
`jobhunt report` static HTML dashboard generator (`design.md` §1).

**Dependencies:** Phase 14 (needs application history to analyze).

**Acceptance Criteria:** Report correctly computes response/interview/
offer rates by role type and source on fixture data; HTML output opens
and renders offline with no network calls.

**Estimated Complexity:** S/M

---

## Phase 17 — Testing & Quality Hardening

**Status:** ⬜ Not started.

**Objectives:** Close coverage gaps and stabilize the full pipeline
before any public release, per `testing.md`.

**Deliverables:** End-to-end pipeline test (`/apply` full run on
fixtures), performance pass on batch operations (Job Search/Matching
over realistic volumes), CI gate on coverage threshold
(`PRD.md` §7 ≥80% on core logic), dependency/secret scanning wired into
CI (`rules.md`).

**Dependencies:** Phases 1–16.

**Acceptance Criteria:** Full pipeline test green on CI; coverage
threshold met; `pip-audit` (or equivalent) clean or explicitly waived
with a documented reason.

**Estimated Complexity:** M

---

## Phase 18 — Deployment & Open-Source Release

**Status:** ⬜ Not started.

**Objectives:** Make the repository genuinely usable by someone who is
not the maintainer.

**Deliverables:** Public-facing `README.md` polish (install steps,
LaTeX distribution setup, quickstart), `CONTRIBUTING.md`, issue/PR
templates, `LICENSE` file applied (`decisions.md` ADR-0009 confirmed),
first tagged release, push to
`https://github.com/sougataresearch/JOB_HUNT`.

**Dependencies:** Phase 17.

**Acceptance Criteria:** A clean clone + documented setup steps alone
(no undocumented tribal knowledge) gets a new machine to a passing
`pytest` run and a successful `/setup` + `/scrape` + `/apply` dry run on
fixture data (`PRD.md` §7 open-source-readiness metric).

**Estimated Complexity:** S/M

---

## Phase Dependency Summary

```
1 Foundation
 ├─▶ 2 Configuration ─▶ 3 Core AI ─┐
 └─▶ 4 Storage & Schemas ──────────┼─▶ 5 CV Analysis ─▶ 6 Skill Gap
                                   │        │
                                   │        └─▶ 7 Job Search ─▶ 8 Job Matching ─▶ 9 Ranking
                                   │                    │              │
                                   │                    └──────────────┼─▶ 10 ATS Optimization
                                   │                                   │        │
                                   │                                   └────────┼─▶ 11 Resume Customization
                                   │                                            │        │
                                   │                                            │        ▼
                                   │                                            │  12 Cover Letters ─▶ 13 Email Automation
                                   │                                                        │
                                   4 ─────────────────────────────────────────▶ 14 Application Tracking ◀┘
                                                                                     │        │
                                                                                     ▼        ▼
                                                                       15 Interview Prep   16 Career Analytics
                                                                                     │        │
                                                                                     └───┬────┘
                                                                                         ▼
                                                                       17 Testing & Quality Hardening
                                                                                         ▼
                                                                       18 Deployment & OSS Release
```

See [`implementation_order.md`](implementation_order.md) for the exact,
file-level build sequence within and across these phases.
