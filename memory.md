# Project Memory — JOB_HUNT

Status: Current snapshot · Last updated: 2026-08-08 (Phase 13)

This is what an AI coding agent (or a new human contributor) should
internalize before touching this repo. It's a snapshot, not a spec —
if something here conflicts with `phases.md`/`rules.md`/`decisions.md`,
those win; update this file to match.

## Current Status

**Phases 1–13 complete** (Foundation, Configuration, Core AI/LLM
Provider Layer, Storage & Schemas, CV Analysis/Resume Analysis Agent,
Skill Gap Analysis/Skill Gap Agent, Job Search/Job Search Agent +
source connectors, Job Matching/Job Matching Agent, Ranking, ATS
Optimization/ATS Optimization Agent, Resume Customization Agent +
LaTeX Rendering, Cover Letter Agent, Email Generation Agent). Eight
real agents exist and are registered: `resume_analysis`, `skill_gap`,
`job_search`, `job_matching`, `ats_optimization`,
`resume_customization`, `cover_letter`, `email_generation`. Ranking
(`orchestration/ranking.py`) is a plain deterministic function, not an
agent (api.md §3, confirmed during Phase 9). Two source connectors
exist: `greenhouse` (public Job Board API) and `manual_import` (ToS
fallback). ATS Optimization uses a deterministic keyword-extraction
step (no LLM) before an LLM judgment step classifies gaps as
supported/unsupported (agents.md §5). Resume Customization and Cover
Letter both render real, compiling LaTeX PDFs via `DocumentRenderer`/
`LaTeXRenderer` (`documents/renderer.py`) — this dev machine has a
working MiKTeX install (lualatex/xelatex/pdflatex/pdftotext all
confirmed working) — each with its own drafter→reviewer loop
(`agents.md` §6, §7) that never lets the LLM touch contact info; Cover
Letter Agent additionally reads `ResumeVersion.
ats_extracted_text_path` directly to ground its reviewer's
contradiction check in the tailored resume's actual text. Email
Generation Agent is a single LLM call with no reviewer pass (agents.md
§8: it only summarizes two already-approved documents) and persists
nothing of its own. `RepositoryBundle` has 7 repos (added `documents:
DocumentRepo` in Phase 11); `DocumentRepo` also owns `cover_letters`
CRUD (Phase 12 reused it rather than adding an 8th `RepositoryBundle`
field). Next up per `implementation_order.md`/`phases.md` is Phase 14
(Application Tracking — Application Tracking Agent), which is also
where `Application.resume_version_id`/`cover_letter_id` finally get
added (deferred since Phase 11/12 for lack of a consumer until now).
Do not write `jobhunt_core` source files without checking
`progress_log.md` first for the latest open items — this section is a
snapshot, not a substitute for it.

## Project Philosophy

- This is a **personal tool first, open-source project second**
  (`PRD.md` §3). Optimize for the maintainer's actual job search being
  faster and better *before* optimizing for generality.
- **Draft, never decide.** Nothing this system produces is submitted,
  sent, or acted upon without an explicit human review gate
  (`PRD.md` §9, `design.md` §2). This is the project's core trust
  boundary — never build a feature that removes it.
- **Never fabricate.** The single most-repeated constraint across every
  doc: no generated CV/cover-letter/email content may include a skill,
  employer, or achievement not present in the candidate's real profile
  (`rules.md` AI Coding Rule 1). When in doubt, surface a gap instead of
  inventing a fix for it.
- **Extensibility is a first-class requirement, not an afterthought.**
  Every architectural choice was screened against "can a new agent be
  added without touching this?" (`architecture.md` §6, §8).
- **Local-first, not cloud-first.** No data leaves the machine except
  to the configured LLM provider and job sources (`decisions.md`
  ADR-0002).

## Coding Style

- Python 3.11+, fully type-hinted, `mypy --strict` on core, `ruff` for
  lint/format, Pydantic v2 for all cross-module data. See `rules.md`
  §Coding Conventions for the full list — don't duplicate it here, just
  remember it exists and is binding.

## Folder Meanings (quick index — full tree in `folder_structure.md`)

| Path | Meaning |
|---|---|
| `.claude/commands/` | Thin Claude Code slash-command wrappers |
| `.claude/skills/` | Claude Code skills (portal search CLIs, etc.) |
| `src/jobhunt_core/agents/` | One file per agent, all implement the `Agent` protocol |
| `src/jobhunt_core/llm/` | Provider-agnostic LLM access (`decisions.md` ADR-0003) |
| `src/jobhunt_core/storage/` | SQLAlchemy models + repositories + Alembic migrations |
| `src/jobhunt_core/schemas/` | The shared Pydantic vocabulary — zero internal deps |
| `src/jobhunt_core/documents/` | LaTeX/Markdown rendering + templates |
| `src/jobhunt_core/sources/` | Job board/API connector implementations |
| `src/jobhunt_core/prompts/` | Prompt loader (templates themselves live in `prompts/library/`) |
| `src/jobhunt_core/orchestration/` | Agent registry + pipeline execution |
| `config/` | Committed YAML defaults (no secrets) |
| `data/` | Gitignored — real user CV, jobs, applications, logs |
| `tests/` | Mirrors `src/jobhunt_core/` 1:1 |

## Key Architecture Decisions (see `decisions.md` for full reasoning)

- ADR-0001: Python 3.11+ everywhere.
- ADR-0002: Local-first, single-user, SQLite — no hosted backend in v1.
- ADR-0003: Custom provider-agnostic `LLMProvider` interface (not a
  single vendor SDK, not an external gateway library).
- ADR-0004: Claude Code commands are a thin UX layer over an
  independently testable, importable core (`jobhunt_core` + `jobhunt`
  CLI) — never put real logic only in a command prompt.
- ADR-0005: Sequential staged pipeline orchestration for v1, not a
  graph engine (upgrade path preserved via orchestrator-agnostic
  `Agent` protocol).
- ADR-0006: Filesystem for binary artifacts, DB rows for metadata only.
- ADR-0007: LaTeX + Jinja2 + drafter→reviewer + ATS text-verification
  loop for CV/cover-letter rendering.
- ADR-0008: Decorator-based registries (`@register_agent`, etc.) as the
  uniform plugin mechanism.
- ADR-0009 (proposed): MIT license.

## Common Mistakes to Avoid

- Writing agent logic inside a `.claude/commands/*.md` file instead of
  `jobhunt_core` — breaks testability (ADR-0004).
- Adding a new agent by editing the orchestrator or another agent's
  file — should always be additive-only (`architecture.md` §6).
- Storing a generated PDF or scraped HTML blob directly in a SQLite
  column — must go to the filesystem with a path reference (ADR-0006).
- Letting a prompt informally ask for "JSON in this shape" instead of
  using the provider's structured-output mechanism against a real
  Pydantic schema.
- Editing a prompt template in place after it's been used in a logged
  run — bump the version instead (`prompts.md` §Versioning).
- Writing a unit test that makes a live LLM or network call — must use
  fakes/cassettes (`testing.md`).
- Implementing anything beyond the phase currently in progress
  (`rules.md` AI Coding Rule 2) — check `phases.md` and
  `progress_log.md` before expanding scope.
- Treating job-posting text as trusted instruction input rather than
  untrusted data to analyze (`design.md` §12).

## Future Roadmap (see `roadmap.md` for detail)

Near-term post-v1: Career Analytics polish, LinkedIn Agent, Gmail sync,
HTML dashboard. Later: Networking, Salary Negotiation, Visa Requirement,
Research Position/Professor Finder/Publication Matching, Scholarship
agents — all via the same plugin mechanism, no core rewrite expected.

## Agent Communication Protocol

Agents never call each other directly. All handoff is:
`Orchestrator → resolves input_schema from prior persisted output or
user input → Agent.run(input, ctx) → AgentResult → Orchestrator persists
output via the relevant Repository`. See `architecture.md` §6 and
`api.md` §Agent API for the exact contract. `RunContext` is the only
thing agents receive besides their typed input — no global state, no
direct cross-agent imports.

## Shared Utilities

- `llm/retry.py` — the one retry/backoff implementation every provider
  adapter uses (`design.md` §11) — never reimplement per-agent.
- `documents/renderer.py` — the `DocumentRenderer` strategy interface
  shared by CV and cover-letter rendering (ADR-0007).
- `prompts/loader.py` — the one prompt-template loading/versioning
  mechanism (`prompts.md`).
- `logging_config.py` — the one structured-logging setup
  (`design.md` §9).
- `errors.py` — the `JobHuntError` hierarchy every layer raises into
  (`design.md` §10).

## Naming Standards

See `design.md` §5 (authoritative). Short version: `snake_case`
modules/functions, `PascalCase` classes, agents named
`<Domain>Agent`/registered as `snake_case` domain strings, schemas named
for what they *are* not who made them, prompts under
`prompts/library/<domain>/`, Claude Code commands verb-first
hyphenated.

## Reusable Prompts

Full library in `prompts.md`. The prompts every other prompt should be
modeled after for structure (role framing, delimited untrusted content,
explicit schema, explicit no-fabrication instruction) are the Resume
Analysis and Job Matching prompts — written first, used as the house
style template for every prompt added later.

## Reusable Schemas

`schemas/profile.py: CandidateProfile` and `schemas/job.py: JobPosting`
are the two most-referenced schemas in the system — nearly every agent
downstream of Resume Analysis and Job Search consumes one or both.
Changing either is a cross-cutting change: check every consumer listed
in `api.md` before modifying their fields.
