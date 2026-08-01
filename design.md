# Design Document — JOB_HUNT

Status: Draft v1.0 · Last updated: 2026-08-02

Related: [`architecture.md`](architecture.md) (system shape) ·
[`database.md`](database.md) (full schema) · [`api.md`](api.md)
(interface contracts) · [`rules.md`](rules.md) (enforced conventions)

## 1. UI Philosophy

JOB_HUNT has **no bespoke GUI in v1** (`decisions.md` ADR-0002,
Local-first CLI/desktop model). Its interaction surfaces are:

1. **Claude Code slash commands** (`.claude/commands/*.md`) — the
   primary, conversational UX. Commands are thin: they describe intent,
   call into `jobhunt_core`, and let Claude Code's own conversational
   loop handle clarification, review, and iteration (mirrors
   MadsLorentzen/ai-job-search's `/setup`, `/scrape`, `/apply` pattern).
2. **A `jobhunt` CLI** (Typer-based) — scriptable, non-interactive,
   used for CI, cron-style batch runs (e.g., nightly job search), and by
   contributors who don't use Claude Code.
3. **A generated static HTML report** (`jobhunt report`) — read-only,
   offline dashboard over the tracking data (applications, statuses,
   response rates). No server process; opened as a local file.

The guiding principle: **every capability must work end-to-end from the
CLI alone.** Claude Code commands are a UX wrapper, never the only path
— this keeps the system testable (`testing.md`) and keeps Claude Code
as an optional, swappable front-end rather than a hard dependency
(`decisions.md` ADR-0004).

## 2. UX Principles

- **Draft, never decide.** Every agent produces a draft artifact
  (score, document, email, tracking update). The user is always shown a
  clear "review this before it's used" gate — no silent auto-submission
  (`PRD.md` §9).
- **Explain, don't just output.** Scoring and ranking agents always
  return a rationale alongside the number (`schemas.MatchScore.rationale`)
  — a bare float is never acceptable output (`rules.md`).
- **Progressive disclosure.** Slash commands default to showing a
  summary (e.g., top 10 ranked postings); full detail is one command
  away (`/rank --detail <id>`), not dumped by default.
- **Idempotent re-runs.** Re-running a command on the same input (e.g.,
  `/apply` on a posting already processed) must detect existing state
  and offer to reuse or regenerate — never silently duplicate records
  (`database.md` unique constraints enforce this at the data layer).
- **Fail loud to the user, fail soft to the pipeline.** If one posting's
  scoring fails, the batch continues and reports the failure per-item;
  it never aborts an entire `/scrape` run for one bad record
  (`design.md` §7 Error Handling).

## 3. Database Design (summary — full schema in `database.md`)

- **Engine:** SQLite (file-based, zero-infra, adequate for single-user
  write volume — `decisions.md` ADR-0002). Access exclusively through
  SQLAlchemy models in `storage/models/`; no raw SQL in agent code
  (`rules.md`).
- **Migrations:** Alembic from the first schema version onward — even
  as a solo dev, so schema evolution is never a manual `ALTER TABLE`
  (`rules.md` §Refactoring Rules).
- **Artifacts vs. rows:** binary/large content (PDFs, LaTeX sources, raw
  scraped HTML) is never stored as a DB blob — rows store a relative
  `file_path` into `data/documents/` or `data/raw/`, and the file is the
  source of truth for content, the DB row for metadata
  (`decisions.md` ADR-0006).
- **Soft state, hard history:** `Application.status` is mutable (current
  state) but every status transition is also appended to an
  `ApplicationEvent` table — status history is never destructively
  overwritten (`database.md` §Application).

## 4. Component Hierarchy

```
Orchestrator
 └─ Pipeline (ordered stage list, per `architecture.md` §3.1)
     └─ Stage (wraps one Agent + its retry/timeout policy)
         └─ Agent (pure logic: input schema → output schema)
             └─ LLMProvider (injected, not constructed by the agent)
             └─ PromptTemplate (loaded by name+version from `prompts/`)
Storage
 └─ Repository (one per aggregate: ProfileRepo, JobRepo, ApplicationRepo…)
     └─ SQLAlchemy Model
Documents
 └─ Renderer (LaTeX or Markdown strategy, chosen by template metadata)
     └─ Template (Jinja2-templated .tex/.md file)
```

Agents never instantiate a `Repository` or `LLMProvider` directly — both
are passed in via `RunContext` (dependency injection, not service
location), which is what makes agents unit-testable with fakes
(`testing.md`).

## 5. Naming Conventions

- **Python:** `snake_case` for modules/functions/variables, `PascalCase`
  for classes, `SCREAMING_SNAKE_CASE` for constants — standard PEP 8,
  enforced by `ruff` (`rules.md`).
- **Agents:** named `<Domain>Agent` (e.g., `ResumeAnalysisAgent`), file
  `agents/<domain>_agent.py`, registry key `snake_case` domain name
  (`"resume_analysis"`) — the registry key is what appears in
  `config/agents.yaml` and CLI subcommands.
- **Schemas:** input schema `<Domain>Input`, output schema
  `<Domain>Output` or a more specific noun when reused elsewhere (e.g.,
  `CandidateProfile` is produced by Resume Analysis but consumed by
  almost everything, so it's named for what it *is*, not who made it).
- **Prompts:** `prompts/library/<agent_domain>/<prompt_name>.md`, each
  with a version suffix directory or frontmatter `version:` field
  (`prompts.md` §Versioning) — never edited in place once a version has
  been used in a logged run (append a new version instead).
- **Claude Code commands:** verb-first, lowercase, hyphenated for
  multi-word (`/apply`, `/scrape`, `/rank`, `/interview-prep`) —
  mirrors the reference repo's convention.
- **Database tables:** plural snake_case (`job_postings`,
  `applications`); model class singular PascalCase (`JobPosting`,
  `Application`) — standard SQLAlchemy convention.
- **Config keys:** lowercase dotted namespace matching directory
  structure (`llm.anthropic.model`, `sources.linkedin.rate_limit_per_min`).

## 6. API Standards (full contracts in `api.md`)

- All internal module boundaries are **typed Python interfaces**
  (Protocols/ABCs), not implicit dict contracts — every input/output is
  a Pydantic model defined in `schemas/`.
- All internal APIs are **synchronous by default**; async is introduced
  only at I/O-bound boundaries where concurrency has a measured benefit
  (e.g., parallel job-source fetches in `sources/`), and is documented
  per-module when used (`decisions.md` ADR to be added if/when this
  happens — not needed for v1's expected load).
- Every public function/class in `jobhunt_core` has a docstring stating
  purpose, args, returns, and raises — enforced by `ruff`'s pydocstyle
  rules (`rules.md` §Documentation Standards... equivalent for this
  project — see `rules.md`).
- No module-level mutable global state; configuration and provider
  instances are constructed once (at CLI/command entry) and threaded
  through via `RunContext`.

## 7. File Organization

See [`folder_structure.md`](folder_structure.md) for the full tree.
Governing principles:
- **One agent, one file** under `agents/` (no god-module holding every
  agent).
- **Tests mirror source layout** 1:1: `src/jobhunt_core/agents/foo.py`
  ↔ `tests/agents/test_foo.py`.
- **User data never lives inside the package tree** — everything under
  `data/` is gitignored; the repo ships templates and code, never a
  real CV or real application history (`rules.md` §Secrets Management,
  `config.md`).
- **Generated documents** (PDFs, compiled LaTeX aux files) live under
  `data/documents/<application_id>/`, one directory per application, so
  a whole application's paper trail can be zipped/deleted atomically.

## 8. Configuration Strategy

Full detail in [`config.md`](config.md). Summary:
- **Layering:** defaults in `config/*.yaml` (checked into git, no
  secrets) → user overrides in `config/local.yaml` (gitignored) →
  environment variables (highest precedence, for secrets and
  CI/deployment overrides) → validated at load time through
  `pydantic-settings` into a single typed `Settings` object.
- **Secrets** (API keys) live only in `.env` / environment variables,
  never in any YAML file that could be committed (`rules.md`).
- **Feature flags** (e.g., enabling an experimental agent) are plain
  booleans in `config/agents.yaml`, read once at startup — no runtime
  remote flag service in v1 (unnecessary complexity for a single-user
  local tool).

## 9. Logging Strategy

- **Structured logging** (JSON lines to `data/logs/jobhunt.log`, human
  readable to stderr) via Python's stdlib `logging` configured in
  `jobhunt_core/logging_config.py` — no third-party logging framework
  needed at this scale.
- **Every agent run emits one structured event** on completion:
  `{run_id, agent, input_ref, prompt_version, model, tokens_in,
  tokens_out, cost_estimate, latency_ms, status, warnings}` — this is
  the audit trail required by `PRD.md` §6 Auditability.
- **Never log secrets or full LLM prompt/response bodies at INFO level**
  — bodies are logged at DEBUG only, gated behind an explicit
  `JOBHUNT_LOG_LLM_BODIES=1` opt-in, because CV/cover-letter content is
  personal data (`rules.md` §Security Rules).
- **Log rotation:** size-based rotation (stdlib
  `RotatingFileHandler`), retained locally only — logs are never
  uploaded anywhere.

## 10. Error Handling

- **Typed exception hierarchy** rooted at `JobHuntError`, with subtypes
  per layer: `LLMProviderError`, `SourceFetchError`, `RenderError`
  (LaTeX compilation failures), `ValidationError` (schema violations),
  `StorageError`. Agents catch only what they can meaningfully act on;
  everything else propagates to the orchestrator's per-stage error
  boundary (`design.md` §2 "fail loud to the user, fail soft to the
  pipeline").
- **Per-item isolation in batch operations:** `Job Search Agent`
  processing 50 postings records failures per-posting
  (`SourceFetchError` on one board does not abort the other 49).
- **LaTeX compile failures are first-class, not exceptions to
  suppress:** the Resume/Cover Letter renderer must surface the actual
  LaTeX log on failure, never silently fall back to a degraded format
  without telling the user (`decisions.md` ADR-0006).
- **User-facing errors are actionable:** every raised `JobHuntError`
  carries a human-readable `.remedy` string (e.g., "ANTHROPIC_API_KEY is
  not set — add it to your .env file") — see `api.md` §Error Envelope.

## 11. Retry Policies

- **LLM calls:** exponential backoff with jitter, max 3 attempts, only
  on retryable errors (429 rate limit, 5xx, timeout) — never retried on
  4xx content-policy or auth errors. Implemented once in
  `llm/retry.py` and shared by every provider adapter, not
  reimplemented per-agent (`config.md` §Rate Limits/Timeouts).
- **Job source fetches:** same backoff policy, plus a circuit breaker
  per source (if a source fails N consecutive times, skip it for the
  rest of the run and report it, rather than stalling the whole
  search — `agents.md` §Job Search Agent Failure Handling).
- **LaTeX compilation:** retried once after attempting an automatic fix
  for known-common issues (e.g., special-character escaping) via the
  drafter→reviewer loop (`decisions.md` ADR-0007 — mirrors reference
  repo's verification loop); a second failure surfaces to the user
  rather than looping indefinitely.
- **No retries** on validation errors (malformed schema) — those are
  bugs or bad input, not transient failures, and retrying would hide
  them.

## 12. Security Considerations

- **Secrets management:** API keys only via environment variables/`.env`
  (gitignored); `.env.example` documents required keys with no real
  values (`rules.md` §Secrets Management, `config.md`).
- **PII handling:** CV content, application history, and generated
  documents are personal data. They live only under gitignored `data/`;
  no telemetry, analytics, or crash-reporting library may transmit this
  content off-device (`PRD.md` §6 Non-Functional Requirements).
- **Prompt-injection awareness:** job posting text is untrusted input
  that flows into LLM prompts. Agents must treat posting content as
  *data to analyze*, never as *instructions to follow* — prompts
  explicitly delimit untrusted content and instruct the model to ignore
  any embedded instructions within it (mirrors the reference repo's
  "agentic defenses are instruction-level" finding; see `prompts.md`
  §Prompt-Injection Guardrails and `rules.md` §Security Rules).
- **Outbound network calls are enumerable:** the only things JOB_HUNT
  ever talks to over the network are (a) the configured LLM provider(s)
  and (b) configured job sources. No other outbound calls are permitted
  without a corresponding `config.md` entry and `decisions.md` ADR.
- **No credential storage for third-party portals in v1:** JOB_HUNT
  never stores a user's job-board login credentials; sourcing uses
  public APIs/feeds or user-provided exports/pastes only (`PRD.md` §9
  Out of Scope, `rules.md`).
- **Dependency hygiene:** `pip-audit` (or equivalent) run in CI against
  `pyproject.toml`-locked dependencies (`rules.md` §Dependency
  Management).
