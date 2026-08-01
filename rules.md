# Development Rules — JOB_HUNT

Status: Binding v1.0 · Last updated: 2026-08-02

These rules are **strict, not advisory**. Any AI coding agent (Claude
Code included) or human contributor working in this repo must follow
them. Where a rule and a convenience conflict, the rule wins — raise it
as a `decisions.md` ADR proposal instead of quietly working around it.

## AI Coding Rules (read first — these override default AI behavior)

1. **Never invent CV content.** No agent may add a skill, employer,
   credential, project, or achievement to any generated document that
   is not present in the candidate's actual `CandidateProfile`. If a
   posting wants something the candidate doesn't have, the correct
   output is a gap noted in `SkillGapReport`/`ATSReport` — never a
   fabricated bullet point. This is the single most important rule in
   this project (`PRD.md` §7 success metric: zero fabricated claims
   shipped).
2. **Never silently expand scope.** If a task is scoped to Phase N
   (`phases.md`), do not implement Phase N+1 functionality "while
   you're in there." Flag it as a follow-up instead.
3. **Never remove a regression/golden test to make a change pass.** If
   a test fails after a change, fix the change or, if the test's
   expectation was genuinely wrong, update it explicitly with a comment
   explaining why — never delete or skip it to unblock a merge
   (`testing.md`).
4. **Never invent a metric, benchmark, or evaluation result.** If asked
   to report test coverage, eval scores, or performance numbers, run
   the actual tooling and report actual output — never approximate or
   present a plausible-sounding number as measured.
5. **Cite the source of a non-obvious design choice.** If a change
   follows from a specific ADR, phase boundary, or PRD requirement,
   name it explicitly in code comments/PR description (e.g., "per
   `decisions.md` ADR-0007, LaTeX rendering must verify PDF text
   round-trip"). If no doc justifies a choice and it's your own
   judgment call, say so explicitly rather than presenting it as
   doc-derived.
6. **Never touch `data/` sample content as if it were fixtures.**
   Real user data (`data/`) and test fixtures (`tests/fixtures/`) are
   different directories with different git treatment — never copy
   real CV/application data into version-controlled fixtures.
7. **Never modify vendored/third-party code** pulled in as a reference
   or dependency; treat anything under a `vendor/`-equivalent or
   installed-package path as read-only.

## Folder Conventions

- `src/jobhunt_core/<layer>/` for all core logic (see
  `folder_structure.md`); nothing runnable lives directly in the repo
  root except entry-point config files (`pyproject.toml`, etc.).
- `tests/` mirrors `src/jobhunt_core/` 1:1 — a new module always ships
  with a corresponding test module in the same relative path.
- `.claude/commands/` and `.claude/skills/` contain **thin** wrappers
  only — no business logic lives in a command's Markdown body beyond
  what's needed to call into `jobhunt_core`/the CLI (`decisions.md`
  ADR-0004).
- `data/` is entirely gitignored; `config/` is entirely committed except
  `config/local.yaml` and `.env`.
- One agent per file under `agents/`; one schema group per file under
  `schemas/` (e.g., `schemas/profile.py`, `schemas/job.py`).

## Coding Conventions

- Python 3.11+, type-hinted throughout; `mypy --strict` on
  `src/jobhunt_core/` (relaxed only for third-party stubs gaps, never
  for our own code).
- Formatting/linting via `ruff` (format + lint), enforced by pre-commit
  and CI — no manual style debates; if `ruff` allows two styles,
  either is fine, don't hand-edit against its output.
- Pydantic v2 for every data model that crosses a module boundary
  (`architecture.md` §2); plain dataclasses are acceptable only for
  purely internal, single-module helper structures.
- Dependency injection over service location: agents receive
  `LLMProvider`/`Repository` instances via `RunContext`, never construct
  or import a global singleton themselves (`design.md` §4).
- No module-level mutable state.

## Naming Conventions

See `design.md` §5 for the full table (agents, schemas, prompts,
commands, tables, config keys). Do not introduce a new naming pattern
without updating that table.

## Prompt Engineering Standards

- Every prompt lives in `prompts/library/<agent>/<name>.md` as a
  versioned template — never inlined as a Python string inside an agent
  file (`prompts.md`).
- Prompts must explicitly delimit untrusted content (job posting text,
  scraped HTML) from instructions, and explicitly instruct the model to
  treat delimited content as data, never as commands to follow
  (`design.md` §12 prompt-injection guardrails).
- Prompts requesting structured output must specify the exact
  Pydantic schema (via the provider's structured-output mechanism), not
  rely on the model to informally follow a described JSON shape.
- Every prompt change is a **new version**, not an in-place edit, once
  it has been used to produce a logged run — old versions are kept so
  past outputs remain reproducible/explainable (`prompts.md`
  §Versioning).
- No prompt may instruct the model to fabricate information not present
  in its inputs (enforced review item, ties to AI Coding Rule 1 above).

## Logging Rules

- Structured JSON event per agent run, per `design.md` §9 — required
  fields: `run_id, agent, prompt_version, model, tokens_in, tokens_out,
  cost_estimate, latency_ms, status`.
- Never log secrets, API keys, or full prompt/response bodies at INFO
  level; bodies only at DEBUG behind an explicit opt-in env var.
- Never log full CV/personal content at any level to a destination that
  isn't the local, gitignored log directory.

## Documentation Rules

- Every public class/function in `jobhunt_core` has a docstring:
  purpose, Args, Returns, Raises.
- Every new agent gets a corresponding entry in `agents.md` before or
  alongside its implementation — not after, as an afterthought.
- Every new prompt gets a corresponding entry in `prompts.md`.
- Every ADR-worthy decision (see `decisions.md` intro) is recorded
  before merging the code that depends on it, not retroactively.
- README/quickstart docs are updated in the same PR as any change to
  setup steps or CLI surface — docs must never silently drift from
  behavior.

## Testing Requirements

Full strategy in `testing.md`. Binding minimums:
- No unit test may make a live network or LLM call — use fakes/recorded
  cassettes.
- Every agent ships with: (a) a schema-validation test, (b) at least one
  golden-file prompt test, (c) a failure-path test (bad input, provider
  error).
- Core (non-LLM) logic maintains ≥80% coverage, enforced in CI
  (`PRD.md` §7).
- A new agent's tests must be addable without modifying any existing
  test file (validates the plugin architecture — `architecture.md` §6).

## Git Workflow

- Trunk-based with short-lived feature branches: `feat/<phase>-<slug>`,
  `fix/<slug>`, `docs/<slug>`, `chore/<slug>`.
- CI (lint, type-check, tests, secret scan, dependency audit) must be
  green before merge.
- Squash-merge feature branches into `main` to keep history readable as
  the project scales toward open-source contributors.
- No direct pushes to `main` once the repo is public
  (`phases.md` Phase 18) — PR required even for the solo maintainer, to
  keep CI as a real gate.

## Commit Standards

- Conventional Commits style: `feat(agents): add Skill Gap Agent`,
  `fix(storage): correct Alembic downgrade for applications table`,
  `docs(phases): add Phase 16 acceptance criteria`.
- Commit body explains **why**, not just what — the diff already shows
  what changed.
- Reference the phase/ADR/issue a commit relates to when non-obvious.

## Branch Strategy

- `main` — always green, always deployable/importable.
- `feat/*`, `fix/*`, `docs/*`, `chore/*` — short-lived, rebased on
  `main` before merge, deleted after merge.
- No long-lived `develop` branch — unnecessary ceremony for this
  project's scale (`rules.md` favors simplicity per `PRD.md` NFRs).

## Error Handling Rules

- Use the typed exception hierarchy (`design.md` §10); never raise a
  bare `Exception` or swallow an exception silently (`except: pass` is
  forbidden — caught exceptions are logged and either re-raised,
  wrapped in a `JobHuntError` subtype, or handled with an explicit,
  commented reason).
- Every user-facing exception carries a `.remedy` string.
- Batch operations isolate per-item failures (`design.md` §10) — never
  let one bad record abort an entire run silently or loudly without
  reporting which item failed.

## Security Rules

- No secret, API key, or token ever appears in source, config
  (non-`local`/`.env` files), logs, or test fixtures.
- CI includes secret scanning (e.g., `gitleaks` or equivalent) and
  dependency vulnerability scanning (`pip-audit`) — both must pass or
  have a documented, time-boxed waiver.
- Job posting / scraped content is untrusted input — treat per
  `design.md` §12 prompt-injection guardrails in every agent that
  consumes it.
- No feature scrapes a source whose Terms of Service prohibit it
  (`PRD.md` §9); when in doubt, prefer an official API or manual
  import over scraping.
- No agent stores third-party portal login credentials (`PRD.md` §9).

## Secrets Management

- All secrets via environment variables, loaded from a gitignored
  `.env`; `.env.example` lists required keys with placeholder values
  only.
- Never commit a real `.env`, real CV, or real application data —
  verified by `.gitignore` plus a CI check that fails the build if a
  path matching `data/**` (excluding `.gitkeep`) is staged.

## Configuration Rules

- Config is layered exactly as specified in `design.md` §8 and
  `config.md` — no ad-hoc `os.environ.get()` calls scattered through
  agent code; all config access goes through the typed `Settings`
  object.
- Adding a new config key requires updating `config.md` and the
  relevant YAML schema/default in the same change.

## Refactoring Rules

- Any schema change to a SQLAlchemy model ships with an Alembic
  migration in the same PR — never a manual production `ALTER TABLE`
  and never a schema drift between code and an existing DB file.
- Renaming a public `jobhunt_core` symbol used by `.claude/commands/`
  or the CLI updates both call sites in the same change — docs and code
  are not allowed to drift (`rules.md` §Documentation Rules).
- No speculative abstraction: don't introduce a plugin/strategy pattern
  for an extension point that has exactly one implementation and no
  concrete plan for a second (mirrors this workspace's general
  no-premature-abstraction principle).

## Dependency Management

- Dependencies pinned via `pyproject.toml` + lockfile; new dependencies
  justified in the PR description (what it replaces or enables).
- Prefer stdlib or an already-present dependency over adding a new one
  for a small need.
- `pip-audit` (or equivalent) run in CI on every PR that touches
  dependencies.

## Performance Guidelines

- Batch operations (job search, batch scoring) should support
  concurrent I/O at the `sources/`/`llm/` boundary where it has a
  measured benefit — do not add async complexity speculatively
  (`design.md` §6 API Standards).
- Respect configured per-run and per-day cost/token ceilings
  (`config.md` §Rate Limits) — an agent must stop and report, not
  silently exceed, a configured budget.
- No agent should require an LLM call for something a deterministic
  function can compute (e.g., keyword-presence checks in `ATSReport`
  should be deterministic string/embedding matching where possible, not
  an LLM call, reserving LLM calls for judgment-requiring steps).

## Code Review Checklist

Before approving any PR (self-review counts while solo, per
`rules.md`'s applicability to a "team of one becoming a team"):

- [ ] Does this stay within its declared phase's scope (`phases.md`)?
- [ ] Are all new public functions/classes docstringed?
- [ ] Are new schemas added to `schemas/` and referenced in
      `database.md`/`api.md` if they cross a module boundary?
- [ ] Do new agents have an `agents.md` entry and versioned prompt(s)
      in `prompts.md`?
- [ ] Are there tests for the happy path, a failure path, and (for
      agents) a golden-file/eval case — with no live network/LLM calls?
- [ ] Does any new exception use the typed hierarchy with a `.remedy`?
- [ ] Are secrets absent from the diff (double-check anything that
      looks like a key, token, or real personal data)?
- [ ] Does a schema change include an Alembic migration?
- [ ] Is a new ADR needed, and if so, is it included?
- [ ] Does the change avoid fabricating CV content anywhere in a
      generated document or test fixture (AI Coding Rule 1)?
