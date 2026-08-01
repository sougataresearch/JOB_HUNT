# Progress Log — JOB_HUNT

Dated log of discussions and decisions. Check the most recent entry's
open `[ ]` items before starting substantive work (mirrors this
workspace's `sougata_solver/progress_log.md` convention).

---

## 2026-08-02 — Initial architecture & documentation pass

**Context:** Maintainer requested a full pre-code architecture and
documentation suite for an AI-powered Job Search Agent, modeled in UX
on `MadsLorentzen/ai-job-search` (Claude Code slash commands, LaTeX
documents, local-first, no hosted backend), to be pushed to
`https://github.com/sougataresearch/JOB_HUNT`. Explicit instruction:
**no application code in this pass — documentation and architecture
only.**

**Decisions locked in this session** (full reasoning in `decisions.md`):
- Python 3.11+ (ADR-0001)
- Local-first, single-user, SQLite (ADR-0002)
- Custom provider-agnostic `LLMProvider` abstraction — Anthropic, OpenAI,
  Ollama (ADR-0003)
- Claude Code commands as a thin UX layer over an independently
  testable core (`jobhunt_core` + `jobhunt` CLI) (ADR-0004)
- Sequential staged pipeline orchestration for v1, graph engine
  deferred (ADR-0005)
- Filesystem for binary artifacts, DB rows for metadata only (ADR-0006)
- LaTeX + Jinja2 + drafter→reviewer + ATS verification for document
  rendering (ADR-0007)
- Decorator-based plugin registries for agents/sources/providers
  (ADR-0008)
- MIT license proposed, not yet finalized (ADR-0009)

**Documents produced:** `README.md`, `PRD.md`, `architecture.md`,
`design.md`, `decisions.md`, `phases.md`, `rules.md`, `memory.md`,
`tasks.md`, `api.md`, `database.md`, `agents.md`, `prompts.md`,
`config.md`, `testing.md`, `roadmap.md`, `folder_structure.md`,
`implementation_order.md`, `final_review.md` (this file).

**Self-review findings** (`final_review.md`) that should be addressed
*during* Phase 1–4 implementation, not after:
- [ ] Enable SQLite WAL mode + busy-timeout when building `storage/db.py`
      (Phase 4, `tasks.md` T4.2) — `final_review.md` §1.1.
- [ ] Add an explicit, tested `discover_plugins()` step before relying
      on the agent/source/provider registries (Phase 1 or when
      `orchestration/registry.py` is first built) — `final_review.md` §1.3.
- [ ] Add a concurrency/batch-call mode to the LLM API before Phase 8
      (Job Matching over batches of postings) ships, with its own ADR
      if the design isn't trivial — `final_review.md` §2.2.

**Open items / not yet decided:**
- [ ] Final license confirmation (MIT vs. alternative) before Phase 18
      (`decisions.md` ADR-0009, `tasks.md` T18.3).
- [ ] Which specific job source(s) to build first for Phase 7
      (`tasks.md` T7.2) — needs a concrete ToS-compliant candidate
      picked before that task starts.
- [ ] Whether Ranking (Phase 9) ends up as a mode of the Job Matching
      Agent or a fully separate agent — deferred to implementation time
      per `phases.md` Phase 9 note.
- [ ] LaTeX distribution setup instructions for Windows specifically
      (maintainer's primary machine) — needed before Phase 18 README
      polish, flagged in `final_review.md` §1.2.

**Not yet done:** No code has been written. `D:\AI JOB\JOB_HUNT\` at
this point contains only the documentation suite listed above. Phase 1
(`phases.md`, `tasks.md`) has not started. The repo has not been
`git init`'d or pushed to GitHub — that requires explicit maintainer
go-ahead per `implementation_order.md` step 46.

**Next session should:** confirm the open items above, then begin
Phase 1 (`phases.md`) per the exact sequence in
`implementation_order.md`, starting at step 1 (T1.1).

---

## 2026-08-02 — Phase 1 (Foundation) complete

**Context:** Maintainer requested the repo be pushed to GitHub (done,
see commit history), then asked to complete Phase 1 — Foundation.

**Built, per `tasks.md` T1.1–T1.5:**
- `pyproject.toml` — `src/` layout, package `jobhunt-core` (import name
  `jobhunt_core`), hatchling build backend, `dev` extra
  (ruff, mypy, pytest, pytest-cov, pre-commit). No runtime dependencies
  yet — deliberately deferred to Phase 2 (pydantic-settings), Phase 3
  (LLM SDKs), Phase 4 (SQLAlchemy/Alembic), per `rules.md` AI Coding
  Rule 2 (don't expand scope beyond the phase in progress).
- `.gitignore`, `.env.example` per `config.md` §Environment Variables
  and `rules.md` §Secrets Management.
- `ruff` (lint + format) and `mypy --strict` configured in
  `pyproject.toml`; `.pre-commit-config.yaml` wired to both plus
  standard hygiene hooks.
- `.github/workflows/ci.yml` — lint, format-check, mypy, pytest on
  every push/PR to `main`.
- Full `src/jobhunt_core/` package tree per `folder_structure.md`:
  `agents/`, `llm/` (+`providers/`), `storage/` (+`models/`,
  `repositories/`), `schemas/`, `documents/` (+`parsers/`), `sources/`,
  `prompts/`, `orchestration/`, `config/` — each an `__init__.py` stub
  with a one-line docstring, no logic yet (T1.4).
- `errors.py` — `JobHuntError` base class only (message + `.remedy`,
  design.md §10); subclasses (`ConfigError`, `LLMProviderError`, etc.)
  deferred to the phase that first needs them.
- `logging_config.py` — `configure_logging(log_dir, level)`: stderr +
  rotating JSON-lines file handler, idempotent within a process
  (T1.5). The per-run structured event (`RunEvent`/`log_run_event`,
  api.md §8) is deferred to Phase 4+ since it needs `schemas/`.
- Tests: `tests/test_smoke.py`, `tests/test_errors.py`,
  `tests/test_logging_config.py`, `tests/conftest.py` (a fixture
  resetting the shared `jobhunt` logger between tests — needed because
  `configure_logging`'s idempotency, correct for production, otherwise
  leaks state across tests).

**Verified, not assumed** (`rules.md` AI Coding Rule 4 — actual tool
output, run in this session):
- `pip install -e ".[dev]"` — succeeds.
- `ruff check .` — all checks passed.
- `ruff format --check .` — all files formatted (after adding
  `extend-exclude = ["*.md"]`: newer ruff formats Python fences
  embedded in Markdown by default, which would have reformatted the
  illustrative pseudocode in `api.md`/`agents.md`/etc. — excluded since
  those docs aren't meant to be strict, runnable Python).
- `mypy` (strict, scoped to `src/jobhunt_core`) — no issues in 16
  source files.
- `pytest` — 5 passed, coverage reported (98% on the current, mostly
  stub tree).
- `pre-commit run --all-files` (after `git add`, since pre-commit only
  sees tracked files) — all 7 hooks pass. The trailing-whitespace hook
  auto-fixed one line in `architecture.md` (trivial, kept).

**Deviation from `tasks.md` T1.6:** not actioned — per its own
definition ("Expected files: none until Phase 18"), it's a checkpoint
to reconfirm before Phase 18, not a Phase 1 deliverable.

**Still open** (carried forward, unchanged from the entry above):
license confirmation, first job source pick, Ranking agent-vs-mode
decision, Windows LaTeX install docs — plus the three `final_review.md`
mitigations (WAL mode, `discover_plugins()`, LLM batch/concurrency
mode), none of which were due in Phase 1 itself.

**Not yet done:** Phase 1 commit has not been pushed yet — next action
in this session is to commit and push. Phases 2+ (`phases.md`) have not
started.
