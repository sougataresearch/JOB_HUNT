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

---

## 2026-08-02 — Phase 2 (Configuration) complete

**Built, per `tasks.md` T2.1–T2.3:**
- `config/llm.yaml`, `config/agents.yaml`, `config/sources.yaml` —
  committed defaults matching `config.md`'s worked examples exactly.
- `config/local.yaml.example` — documents the gitignored personal-
  override file (`design.md` §8's second layer); not explicitly listed
  in `tasks.md` T2.1 but present in `folder_structure.md` and needed to
  make the override layer usable/testable.
- `src/jobhunt_core/config/settings.py` — `Settings` (pydantic-settings)
  + `load_settings()`. YAML defaults and `local.yaml` are merged with an
  explicit recursive deep-merge in plain Python *before* ever
  constructing `Settings` (passed as constructor kwargs), rather than
  via pydantic-settings' built-in `YamlConfigSettingsSource` — chosen
  because that library mechanism arbitrates an entire top-level field
  per source rather than deep-merging nested keys across sources, which
  would let a `local.yaml` override of one agent's `enabled` flag wipe
  out every sibling agent from the defaults. Env vars/`.env` use
  pydantic-settings' ordinary precedence since they don't overlap in
  field names with the YAML-sourced `llm`/`agents`/`sources` fields.
- `src/jobhunt_core/config/secrets.py` — `redact()` display helper
  (tasks.md T2.2).
- `ConfigError(JobHuntError)` added to `errors.py` (design.md §10).
- Tests: `tests/config/test_settings.py` (7 cases covering all three
  precedence layers plus the missing-secret and disabled-agent paths),
  `tests/config/test_secrets.py`.

**Real bug caught by the tests, fixed before commit:** the first cut of
`_validate_required_secrets()` fell back to `llm.default_provider` for
any enabled agent with no explicit `provider` set. That's wrong per
`config.md`'s own worked example — `job_search`/`application_tracking`
deliberately omit `provider` *because they don't require an LLM at
all*, not because they should inherit the default. Fixed to only
enforce a secret requirement for agents with an explicit `provider`
field; `test_disabled_agent_does_not_require_secret` is what caught the
original bug (it failed against the real intent before the fix).

**Verified, not assumed** (`rules.md` AI Coding Rule 4): `ruff check`,
`ruff format --check`, `mypy` (strict), `pytest` (15 passed), and
`pre-commit run --all-files` all pass. Also ran `load_settings()`
against the real `config/` files directly (not just test fixtures): it
correctly raises `ConfigError` with no `ANTHROPIC_API_KEY` set, and
correctly loads all 11 v1 agents as enabled once the key is set.
One tooling snag: the `mypy` pre-commit hook runs in its own isolated
venv and doesn't see the project's installed dependencies — added
`additional_dependencies` (pydantic, pydantic-settings, types-PyYAML)
to `.pre-commit-config.yaml`'s mypy hook to fix.

**Doc reconciliation:** `config.md`'s "Rate Limits & Cost Ceilings"
section was ambiguous about which YAML file `limits:` lives in (it
wasn't one of `tasks.md` T2.1's three named files) and duplicated
sources.yaml's per-source rate limiting under a separate global key.
Resolved: `limits` nests under `llm:` in `llm.yaml`; the redundant
global `job_source_rate_limit_per_min` was dropped in favor of the
per-source `rate_limit_per_min` already in `sources.yaml`. Edited in
the same change per `rules.md` §Configuration Rules.

**Deviation from `tasks.md` T2.3:** its completion checklist references
disabling an agent making it "absent from `AgentRegistry.available()`"
— `orchestration/registry.py` doesn't exist yet (not a Phase 2
deliverable). Implemented and tested `Settings.enabled_agent_names()`
as the config-layer equivalent instead; a real `AgentRegistry`
integration test should be added once `orchestration/registry.py` is
built (flagged here so it isn't forgotten, same pattern as the T1.6
deferral last phase).

**Still open:** everything carried from the previous entry, unchanged
(license confirmation, first job source pick, Ranking agent-vs-mode
decision, Windows LaTeX docs, WAL mode, `discover_plugins()`, LLM batch
mode) — none due yet. Added to that list: the `AgentRegistry`-level
test noted above, due whenever `orchestration/registry.py` is built.

**Not yet done:** commit/push for this phase — next action. Phase 3
(Core AI / LLM Provider Layer) has not started.

---

## 2026-08-02 — Phase 3 (Core AI / LLM Provider Layer) complete

**Built, per `tasks.md` T3.1–T3.5:** `LLMProvider` Protocol +
`LLMResponse`/`StructuredLLMResponse` (`llm/provider.py`,
`llm/types.py`); the shared `call_with_retry()` backoff policy
(`llm/retry.py`, algorithm-only, provider-agnostic — each adapter
supplies its own `is_retryable` classifier since 429/5xx/timeout
exception *types* differ per SDK); `AnthropicProvider`, `OpenAIProvider`,
`OllamaProvider` (`llm/providers/`), each registered via
`@register_provider` and structured-output-capable. `LLMProviderError`
added to the exception hierarchy. Extended Phase 2's `ProviderConfig`
with `cost_per_mtok_in`/`cost_per_mtok_out` (default `0.0` — see below).

**On "recorded cassettes" (tasks.md T3.2/T3.3 wording) — an explicit,
honest deviation:** this environment has no real Anthropic/OpenAI API
credentials, so a genuine live-traffic recording was not possible, and
fabricating one would violate `rules.md` AI Coding Rule 4. Instead:
real `anthropic.Anthropic`/`openai.OpenAI` client instances are
constructed with an `httpx.MockTransport` swapped in for the HTTP
layer, so the actual SDK code (request building, response parsing,
exception typing) runs for real — only the network round-trip is
faked. Before writing each adapter, the exact request/response/error
JSON shapes were verified empirically against the *installed* SDK
versions (anthropic 0.120.2, openai 2.52.0) via throwaway scripts, not
assumed from training memory — e.g. confirmed that a 429 with
Anthropic's error envelope really does raise `anthropic.RateLimitError`
with `isinstance` true, that a `tool_use` block's `.input` is already a
plain dict, and that OpenAI's `response_format=json_schema` round-trips
correctly. This is real, high-fidelity integration coverage, just not
literally a "recorded cassette" — flagging the terminology gap rather
than silently reinterpreting the task.

**Real bug the MockTransport approach caught, fixed before commit:** the
first test helper built a raw `anthropic.Anthropic`/`openai.OpenAI`
client without `max_retries=0`, so the SDK's own default internal
retries (max_retries=2, i.e. 3 attempts) compounded with jobhunt's own
`call_with_retry` loop — a persistent-500 test expected 2 total HTTP
calls and got 6. Fixed by matching what the adapters themselves do:
always construct the real client with `max_retries=0` so jobhunt's
retry policy has exclusive control, exactly the "don't double up"
design.md §11 already called for — this is a concrete, verified
demonstration of why that rule exists, not just a stated principle.

**Ollama adapter is lower-confidence than the other two, and this is
stated in its own module docstring:** no live Ollama server is
available in this environment, so its `/api/generate` request/response
shape follows training knowledge of Ollama's documented REST API, not
an empirically confirmed live response (unlike Anthropic/OpenAI, which
were verified against the real installed SDKs). Its tests exercise the
adapter's own logic thoroughly via `httpx.MockTransport`, but that only
proves internal consistency with the *assumed* shape, not fidelity to
a real server. Matches tasks.md T3.4's own "documented as best-effort"
framing — recorded here so this caveat isn't lost. Should be smoke-
tested against a real local Ollama install before anyone relies on it.

**Cost accounting is 0.0 by default, deliberately:** rather than
hardcode a per-model pricing table (a figure I have no verified,
current source for — `claude-sonnet-5`/`gpt-5` are recent enough that
guessing a $/Mtok rate would risk presenting a fabricated number as
fact, `rules.md` AI Coding Rule 4), `cost_per_mtok_in`/`out` live in
`config/llm.yaml` as user-filled data, defaulting to `0.0` (=
"unknown"), not an invented estimate.

**Verified, not assumed:** `ruff check`, `ruff format --check`, `mypy`
(strict), full `pytest` (41 passed, 99% coverage), and
`pre-commit run --all-files` (after adding the new SDKs to the mypy
hook's `additional_dependencies`, same isolated-venv issue as Phase 2).

**Deviation from `tasks.md` T3.1:** no `build_provider_from_settings`-
style factory connecting `Settings.llm.providers[name]` to a
constructed adapter instance was added — that wiring naturally belongs
where `RunContext` is built (orchestration, once agents exist,
Phase 5+); building it now would have no real caller yet
(`rules.md` no-speculative-abstraction). Each adapter's constructor
takes its own explicit args and is fully unit-testable standalone.

**Still open:** everything carried from prior entries, unchanged
(license confirmation, first job source pick, Ranking agent-vs-mode
decision, Windows LaTeX docs, WAL mode, `discover_plugins()` for
*agents* specifically — the LLM provider package now has its own
explicit-import discovery, done this phase — LLM batch/concurrency
mode, `AgentRegistry`-level test). Added: smoke-test the Ollama adapter
against a real local server before relying on it; add real per-model
pricing to `config/llm.yaml` once verified figures are available.

**Not yet done:** commit/push for this phase — next action. Phase 4
(Storage & Schemas) has not started.

---

## 2026-08-02 — Phase 4 (Storage & Schemas) complete

**Built, per `tasks.md` T4.1–T4.4:** Pydantic schemas for the 6 named
aggregates (`schemas/{profile,job,match,ats,application,interview}.py`)
plus their natural sub-entities (`Company`, `ApplicationEvent`,
`InterviewQuestion`) — 9 SQLAlchemy tables total
(`storage/models/`), an Alembic setup with the initial migration
(`migrations/versions/0001_initial.py`), and 6 repositories
(`storage/repositories/`). `storage/db.py` builds the SQLite engine.

**Scope boundary, stated explicitly (not silently):** `database.md`
documents 17 tables total; Phase 4 builds the 6 aggregates
`tasks.md` T4.1 names plus their directly-owned sub-tables. Not built
yet, deferred to the phase that needs them: `users` (multi-user work,
unscheduled — `user_id` stays a plain nullable column with no FK, per
`database.md` §1's own framing), `resume_versions`/`cover_letters`/
`templates` (Phase 11/12), `prompt_versions`/`agent_runs` (once an
agent actually runs, Phase 5+), `search_runs` (Phase 7), `notes`
(unscheduled). `Application.resume_version_id`/`cover_letter_id` and
`JobPosting.search_run_id` are likewise omitted until their target
tables exist — each addition will be its own Alembic migration when
the time comes, which is the normal, expected way this schema grows
(`rules.md` §Refactoring Rules), not a shortcut.

**Applied `final_review.md` §1.1 (SQLite WAL mode)** as committed to
in the Phase 1 log: `storage/db.py`'s `create_sqlite_engine()` sets
`PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` on every
connection. While there, also enabled `PRAGMA foreign_keys=ON` —
SQLite doesn't enforce declared foreign keys by default, so without
this the FK constraints in the models would have been documentation
only, not real, failing `tasks.md` T4.2's "constraints match
database.md exactly" checklist item in spirit if not in schema DDL.
Verified with a real FK-violation test
(`test_foreign_key_enforced_for_missing_job_posting`), not assumed.

**Real bug mypy caught, fixed before commit:** `ApplicationRepo` and
`InterviewRepo` each define a method named `list()` (required by the
api.md §7 Storage API contract). Any *later* method in the same class
returning a bare `list[...]` type — `list_events()`, `list_questions()`
— had that annotation misresolved by mypy against the `list` *method*
instead of the builtin type ("Function ... .list is not valid as a
type"), because mypy resolves forward-reference annotations against
the enclosing class scope, and the method name shadows the builtin
within that scope for everything defined after it. Fixed by qualifying
those two return types as `builtins.list[...]` (ruff's own suggested
fix, confirmed it also satisfies mypy) instead of renaming the `list()`
method, which would have broken the documented Repository contract.

**Verified, not assumed:** `ruff check`, `ruff format --check`, `mypy`
(strict, 44 source files), full `pytest` (67 passed, 94% coverage
overall), `alembic upgrade head` / `alembic downgrade base` both run
for real against a scratch temp DB (not just asserted) and correctly
create/drop all 9 tables, and `pre-commit run --all-files` (added
SQLAlchemy/alembic to the mypy hook's `additional_dependencies`, same
isolated-venv pattern as Phases 2–3).

**Doc reconciliation:** `api.md` §7's `RepositoryBundle` example was
missing `ats: ATSRepo` (an oversight from when that doc was written,
before ATS was confirmed as one of `tasks.md` T4.4's 6 named
aggregates) — added, with a note that assembling the bundle itself is
Phase 5+ work (needs `RunContext`, which doesn't exist until agents
do).

**Housekeeping:** a scratch `data_alembic_scratch/jobhunt.db` file
(created while manually generating the initial migration with
`alembic revision --autogenerate`) was caught in `git status` before
commit and removed rather than staged — a reminder that manual
one-off commands outside the test suite don't get pytest's automatic
`tmp_path` cleanup.

**Still open:** everything carried from prior entries (license
confirmation, first job source pick, Ranking agent-vs-mode decision,
Windows LaTeX docs, `discover_plugins()` for agents, LLM
batch/concurrency mode, `AgentRegistry`-level test, Ollama live-server
smoke test, real LLM pricing). WAL mode is now done, removed from the
open list.

**Not yet done:** commit/push for this phase — next action. Phase 5
(CV Analysis / Resume Analysis Agent) has not started.

---

## 2026-08-05 — Phase 5 (CV Analysis / Resume Analysis Agent) complete

**Built, per `tasks.md` T5.1–T5.3:** `documents/parsers/` (PDF via
`pdfplumber`, DOCX via `python-docx`, Markdown via a shared
section-splitting heuristic) with explicit-import registration;
`prompts/loader.py` (the on-disk `---`-frontmatter + `## System`/
`## User Template` format `prompts.md` already specified) plus the
first real prompt file (`prompts/library/resume_analysis/
extract_profile/1.0.md`); the foundational agent infrastructure
`agents/base.py` (`Agent` Protocol, `RunContext`, `AgentResult`,
`RepositoryBundle`) and `orchestration/registry.py`/`context.py` (the
`@register_agent` mechanism and the `Settings`→`LLMProvider` factory
explicitly deferred in Phase 3); the first real agent,
`ResumeAnalysisAgent`; a `cli/` package (`python -m cli.main setup
<cv>`) and `.claude/commands/setup.md`. Also added 9 fixture CVs (3
personas × 3 formats) under `tests/fixtures/cvs/`, generated by a
committed script (`_generate.py`) rather than hand-built binaries.

**Two real, previously-latent bugs caught by tests written this
phase, both fixed before commit:**
- `agents/base.py`'s `Agent` Protocol needed `InT` contravariant and
  `OutT` covariant (mypy: "Invariant type variable used in protocol
  where contravariant one is expected") — and even correctly variant,
  a registry typed `dict[str, type[Agent[BaseModel, BaseModel]]]` still
  can't soundly hold classes with narrower concrete input/output types
  (a real Python-typing limitation for heterogeneous Protocol
  registries, not a mistake) — resolved by typing the registry as
  `type[Agent[Any, Any]]`, the standard escape hatch for exactly this
  case, documented in `orchestration/registry.py`.
- **`Settings` fields with a `validation_alias` (`data_dir`,
  `anthropic_api_key`, etc.) silently ignored their plain attribute
  name when constructing `Settings(...)` directly** — `extra="ignore"`
  swallowed the kwarg with no error, falling back to the field
  default. Invisible throughout Phases 2–4 because every prior test
  went through `load_settings()` (env vars/YAML), never direct kwarg
  construction. Surfaced by `tests/cli/test_setup_command.py`
  constructing `Settings(data_dir=tmp_path, ...)` for dependency
  injection: the persisted DB silently landed in the real `./data/`
  directory instead of the test's temp dir. Fixed by adding
  `populate_by_name=True` to `Settings.model_config`; added a
  dedicated regression test to `tests/config/test_settings.py` (Phase
  2's suite) so this can't regress silently.

**A real footgun avoided while writing tests, not a bug in shipped
code:** sharing `FakeLLMProvider` across `tests/agents/`,
`tests/orchestration/`, and `tests/cli/` via a plain importable module
(`tests/support/fake_llm.py`) failed at collection time
(`ModuleNotFoundError: No module named 'tests.support'`) — none of
this project's test directories have `__init__.py` files, so
cross-directory absolute imports don't resolve under pytest's default
import mode without restructuring the whole `tests/` tree. Fixed the
idiomatic way: moved `FakeLLMProvider` into the top-level
`tests/conftest.py` behind a `fake_llm_factory` fixture, which pytest
auto-discovers in any subdirectory with no import-path concerns.
Separately, `tests/cli/` needed `cli/` (not part of the installed
`jobhunt_core` package) to be importable at all — fixed with
`pythonpath = ["."]` in `[tool.pytest.ini_options]`.

**Doc reconciliation:** `architecture.md` §2's module-dependency table
was missing `documents/` from `agents/`'s dependencies and
`config/`/`llm/` from `orchestration/`'s — both real omissions from the
original draft, caught while wiring the Resume Analysis Agent (which
needs CV parsers) and `build_run_context` (which needs `Settings` and
`LLMProvider`). Fixed with a note explaining why.

**Honest limitation, stated directly (not glossed over):** every
agent-level test uses `FakeLLMProvider` with a hand-scripted "correct"
extraction. This proves the agent's own plumbing (file dispatch,
prompt rendering, response assembly, persistence, the "explicit
not-found" pass-through for the sparse fixture) is correct — it cannot
prove a *real* LLM call against the actual prompt produces good
extractions, or that a real LLM would actually leave fields null for
the sparse CV rather than guessing. That requires either live API
credentials (not available in this environment) or a recorded-cassette
eval harness, neither of which exists yet. `testing.md` §3's AI
Evaluation golden-file approach remains aspirational for this agent
until one of those is set up.

**Verified, not assumed:** `ruff check`, `ruff format --check`, `mypy`
(strict, now scoped to `src/jobhunt_core` *and* `cli/` — broadened this
phase since `cli/` has real logic), full `pytest` (114 passed, 94%
coverage), `pre-commit run --all-files` (added pdfplumber/python-docx/
Jinja2/typer to the mypy hook's `additional_dependencies`). Manually
verified `build_run_context` end-to-end against the real `config/`
files and a scratch DB (real `AnthropicProvider` constructed, no live
call made), and the CLI's `--help` output.

**Deviation, stated explicitly:** the `LLMProvider.complete`/
`complete_structured` signatures still take one flat `prompt: str`
(no native `system` parameter) — `prompts/loader.py` concatenates
system+user into one string rather than reopening Phase 3's
already-shipped-and-tested adapters for a caching optimization
(config.md's Anthropic prompt-caching mention) that Phase 5 doesn't
strictly need. Logged as a future enhancement, not silently dropped.

**Still open:** everything carried from prior entries (license
confirmation, first job source pick, Ranking agent-vs-mode decision,
Windows LaTeX docs, `discover_plugins()` for agents — now done, this
phase's registry uses the same explicit-import pattern — LLM
batch/concurrency mode, `AgentRegistry`-level test — now done, see
`tests/orchestration/test_registry.py` — Ollama live-server smoke
test, real LLM pricing). Added: a real eval/cassette harness for
agent-level prompt quality (see honest-limitation note above); native
system-prompt support on `LLMProvider` if/when prompt caching matters;
confirm `populate_by_name=True` didn't mask any other aliased-field
assumptions elsewhere in the codebase (a quick audit, not expected to
find anything, but not yet done).

**Not yet done:** commit/push for this phase — next action. Phase 6
(Skill Gap Analysis) has not started.

## 2026-08-05 — Phase 6 (Skill Gap Analysis / Skill Gap Agent) complete

**Built, per `tasks.md` T6.1:** `schemas/skill_gap.py`
(`SkillGapPriority`, `SkillGap`, `SkillGapReport`); the prompt file
`prompts/library/skill_gap/analyze/1.0.md`; the second real agent,
`SkillGapAgent` (`agents/skill_gap_agent.py`), registered via the same
explicit-import pattern in `agents/__init__.py`. Per
`implementation_order.md` step 21 ("should reuse [Resume Analysis's]
structure directly"), it follows the exact same shape: `SkillGapInput`
→ `load_prompt`/`render_prompt` → `ctx.llm.complete_structured` →
`AgentResult`. `SkillGapInput` accepts either a `target_role` string or
a `list[JobPosting]` (agents.md §2's documented "target role text or
list[JobPosting]" contract), validated at the model boundary so at
least one must be given. Also built the golden-file eval harness
`testing.md` §3 describes and Phase 5 explicitly deferred
("`testing.md` §3's AI Evaluation golden-file approach remains
aspirational... until [live credentials or a cassette harness]" —
still true here, but the *harness* itself now exists): three fixture
cases under `tests/eval/skill_gap/cases/*.yaml` (a clear-gap case, an
`insufficient_data` sparse-profile case per agents.md §2 Failure
handling, and a close-match minor-gap case), each pairing a realistic
`CandidateProfile`/target-role fixture with a hand-curated golden
report and structural `expected_properties`, run through
`tests/eval/skill_gap/test_skill_gap_eval.py`.

**Real, if small, duplication caught and fixed:** Resume Analysis's
private `_default_model(ctx)` helper got copy-pasted verbatim into
`SkillGapAgent` while following its structure — two identical private
functions is exactly the "used twice already, not hypothetically"
case rules.md's no-speculative-abstraction guidance doesn't rule out.
Moved it to `agents/base.py` as `default_model_for(agent_name, ctx)`
and updated both agents to call it, so a third/future agent has one
place to use, not a third copy to drift from.

**Real environment/tooling issue found and fixed, unrelated to this
phase's own code:** running `ruff check` surfaced an import-order
finding in `tests/cli/test_setup_command.py` (a Phase 5 file untouched
this session) that Phase 5's own "verified, not assumed" ruff run had
not flagged. Root cause: the local dev `.venv` has ruff 0.16.1
installed, while `.pre-commit-config.yaml` pins the ruff hook at
`v0.6.9` — the two versions disagree on how to classify `cli.commands.
setup`'s import group, because `cli/` was never listed in `pyproject.
toml`'s `[tool.ruff] src` (only `["src", "tests"]`), so isort-style
first-party detection couldn't resolve it either way and different
ruff versions guessed differently. Running `--fix` with the local
0.16.1 and then with the pinned pre-commit hook produced two *different*
"fixed" orderings for the same import block — a real oscillation, not
a fluke. Fixed at the root cause: added `"."` (the repo root, so `cli`
resolves as a first-party package alongside `src/jobhunt_core`) to
`[tool.ruff] src`, which made both ruff versions converge on the same
ordering, confirmed by re-running `ruff check --fix` with the local
version and then `pre-commit run --all-files` with the pinned one back
to back with no further changes from either.

**Doc reconciliation:** `prompts.md` §8's draft system prompt didn't
mention the `insufficient_data`/empty-`gaps` behavior agents.md §2's
Failure handling section requires — the shipped prompt file adds it
(matching how Phase 5's `extract_profile` prompt also extended its
own draft). Updated `prompts.md` §8 with a note explaining the
addition, same pattern as prior phases' doc reconciliations.

**Honest limitation, carried forward and made concrete:** the new
`tests/eval/skill_gap/` golden-file cases use `fake_llm_factory`
scripted with hand-written "golden" `SkillGapReport`s, not a live model
call or a recorded cassette. This proves the agent's assembly and the
`expected_properties` grading logic are correct end-to-end against
realistic fixtures — it does **not** prove a real LLM, given the
actual shipped prompt, would produce gaps this well-grounded, or
correctly recognize a sparse profile as `insufficient_data` rather
than fabricating gaps. Same caveat as Phase 5's agent tests, now
explicitly wired into the `testing.md` §3-shaped harness so that
swapping in a recorded-cassette `LLMProvider` later upgrades these
same cases to a true model-quality eval without rewriting the test
file — still on the "still open" list below.

**Verified, not assumed:** `ruff check` (0 errors, both ruff versions
agreeing after the `src` fix above), `ruff format --check`, `mypy`
--strict (61 source files, no issues), full `pytest` (124 passed, up
from 114 — 95% coverage), `pre-commit run --all-files` (all 7 hooks
green, no new `additional_dependencies` needed — no new runtime deps
this phase).

**Another stale-doc finding, older than this phase:** `memory.md`
("Status: Current snapshot") still read "Architecture and
documentation phase — no application code exists yet... Phase 1 has
not started," dated 2026-08-02 — stale since before Phase 1 even
began, and never corrected across Phases 1–5. Since `CLAUDE.md`
explicitly names it as the file to check "before assuming what's done
vs. pending," leaving it wrong actively misleads the next session.
Updated its Current Status section and date.

**No architecture.md change needed this phase:** unlike Phase 5,
`SkillGapAgent` only needed `schemas/` (already a documented `agents/`
dependency) and no new module — `architecture.md` §2's table was
checked and found accurate as-is.

**Still open:** everything carried from Phase 5 (license confirmation,
first job source pick, Ranking agent-vs-mode decision, Windows LaTeX
docs, Ollama live-server smoke test, real LLM pricing, native
system-prompt support on `LLMProvider`, a quick audit of
`populate_by_name=True`'s blast radius). The eval harness now exists
but still needs a recorded-cassette or live-credential `LLMProvider`
before its cases test real prompt quality rather than agent plumbing
(see honest-limitation note above) — this applies to every future
agent's eval suite too, not just Skill Gap's.

**Not yet done:** commit/push for this phase — next action. Phase 7
(Job Search) has not started.

## 2026-08-07 — Phase 7 (Job Search — Job Search Agent + Source Connectors) complete

**Context:** User asked to continue through Phases 7, 8, and 9 in one
request. Each phase is still implemented, verified, and logged as its
own unit (own progress_log entry, own commit) — the request just
removed the per-phase "yes, continue" pause between them.

**Resolved a carried-forward open item:** "which specific job source
to build first" (open since the 2026-08-02 entry) — already
effectively decided in the doc phase: `config/sources.yaml` and
`config.md` both already named `greenhouse` as the enabled source.
Confirmed the [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html)
is public, unauthenticated, and documented for exactly this use
(companies use it to power their own public careers pages) — ToS-
compliant per `rules.md` §Security Rules ("prefer an official API...
over scraping"). Logged here as the explicit confirmation that item
asked for.

**Built, per `tasks.md` T7.1–T7.4:**
- `sources/base.py` — `JobSource` Protocol + `@register_source`
  registry, mirroring `llm/provider.py`'s exact shape.
- `sources/greenhouse_source.py` — polls every configured board
  (Greenhouse has no cross-company keyword search), strips HTML via a
  regex tag-strip (no new dependency for a small need, rules.md
  §Dependency Management), filters client-side by keyword/location,
  and has its own **per-board circuit breaker** (N consecutive
  board-fetch failures trips it, remaining boards for that source are
  skipped for the rest of the run, whatever was already fetched is
  kept).
- `sources/manual_import_source.py` — the ToS fallback: wraps a
  caller-supplied batch of already-collected postings (the *human*
  pastes/downloads, JOB_HUNT never fetches on their behalf, sidestepping
  scraping-ToS entirely). `ManualImportItem.from_file()` reuses the CV
  document parsers for raw-text extraction — proved the "get text out
  of a file" logic isn't CV-specific. Deliberately did **not** build
  agents.md §3's *optional* LLM-assisted title/company extraction for
  messy pastes — T7.3 is scoped Difficulty: S, and that's a documented,
  disclosed trim, not a silent one (rules.md AI Coding Rule 2).
- `schemas/job.py` additions — `SearchQuery`, `RawPosting` (api.md
  §2, verbatim), `SearchRun` (database.md §17), plus the
  `JobPosting.search_run_id` field Phase 4 deliberately deferred.
- `storage/models/job.py`'s `SearchRunModel` + `job_postings.
  search_run_id` FK, `JobRepo.create_search_run`/`complete_search_run`/
  `get_search_run` (bundled into `JobRepo`, not a 7th `RepositoryBundle`
  repo — same reasoning already applied to `Company` in Phase 4).
- `orchestration/context.py`'s `build_sources()` (mirrors
  `build_llm_provider()`'s explicit if/elif dispatch) and
  `agents/base.py`'s `RunContext.sources: dict[str, JobSource]`
  (default `{}`, so every pre-Phase-7 `RunContext(...)` call site stays
  valid unchanged).
- `agents/job_search_agent.py` — `JobSearchAgent`, with **two dedup
  layers** per database.md §5: primary `(source, source_id)` (a re-run
  never re-inserts the same posting), secondary fuzzy
  `(company, title, location)` + content hash (flags likely
  cross-source duplicates as an `AgentResult.warnings` entry, keeps
  both rows — "flags... without merging automatically," not silently
  dropped or merged). Per-source failure isolation (design.md §10): one
  source raising `SourceFetchError` is caught and skipped, the batch
  continues.

**A real, load-bearing SQLite gap found while writing the migration,
not assumed away:** the autogenerated migration for `search_runs` +
`job_postings.search_run_id` used `op.create_foreign_key(None, ...)`
directly on the already-existing `job_postings` table — running it
raised `NotImplementedError: No support for ALTER of constraints in
SQLite dialect`. SQLite cannot `ALTER TABLE ADD CONSTRAINT` at all;
`0001_initial.py` never hit this because every constraint there was
declared inline in a `CREATE TABLE`. Fixed by rewriting the migration
with `op.batch_alter_table(...)` (Alembic's copy-and-move strategy),
verified for real: upgrade, downgrade to `0001`, and re-upgrade to
`head` all round-trip cleanly against a scratch DB (`tests/migrations/
test_alembic.py`'s two new tests). Also added `render_as_batch=True`
to both of `migrations/env.py`'s `context.configure()` calls so every
*future* `alembic revision --autogenerate` involving a constraint
change on an existing table produces batch-mode SQL automatically,
instead of silently regenerating the same broken pattern next time.

**A real bug caught before it shipped, not just after:** the first
draft of the fuzzy-dedup key compared the *new* posting's raw company
**name string** (e.g. `"gitlab"`, the Greenhouse board token) against
existing postings' **`company_id`** (a UUID) — these can never match,
silently defeating the entire secondary-dedup check. Caught while
writing this log entry's own description of the logic, before a test
was even run against it. Fixed by resolving `company_id` for the new
posting *before* computing the dedup key, so both sides compare the
same kind of value (`JobRepo.get_or_create_company`'s exact-name
identity), and added `test_fuzzy_duplicate_across_sources_is_flagged_
not_merged` specifically to pin this down.

**Doc reconciliation, several real gaps this time:**
- `architecture.md` §2's prose dependency table was missing `sources/`
  from `agents/`'s row — but §7's own mermaid graph *already* had the
  correct edge (`sources --> agents`), meaning the two sections of the
  same doc already disagreed with each other before this phase, not
  something Phase 7 introduced. Fixed the prose table to match the
  graph, and added `sources --> orchestration` and `documents -->
  sources` edges the graph was missing (orchestration/context.py
  imports `jobhunt_core.sources` directly; `ManualImportSource.
  from_file()` imports `documents.parsers`).
- Documented the one narrow, deliberate exception to "nothing outside
  `agents/` imports from `agents/`": `sources/base.py`'s `JobSource`
  Protocol needs `RunContext` (defined in `agents/base.py`) for its
  `search()` signature per api.md §2 — resolved via a
  `TYPE_CHECKING`-only import (never evaluated at runtime, so the
  actual runtime dependency stays one-directional, `agents/` →
  `sources/`, matching the rule's intent).
- `config.md` §Source Configuration and `config/sources.yaml` gained
  `boards` (Greenhouse-specific, documented as such).

**Honest limitation, stated directly:** `GreenhouseSource`'s request/
response shape is verified against Greenhouse's own public API
documentation and a MockTransport-based test suite, not a live call
(same category of limitation as Phase 3's LLM adapters and Phase 5's
Ollama adapter — no live network access in this environment).
`rate_limit_per_min` is configured but not yet enforced by the
connector itself (not in T7.2's checklist; logged as a deferred
enhancement, not silently dropped).

**Verified, not assumed:** `ruff check`, `ruff format --check`, `mypy
--strict` (65 source files), full `pytest` (156 passed, up from 124 —
95% coverage), `pre-commit run --all-files` (all 7 hooks green, no new
`additional_dependencies` needed — no new runtime deps this phase).
Both Phase 7 acceptance criteria verified by dedicated tests: rerunning
search with overlapping results produces zero duplicate rows
(`test_rerun_with_overlapping_results_produces_no_duplicate_rows`), and
a simulated always-failing source trips the circuit breaker without
aborting the batch (`test_circuit_breaker_stops_after_n_consecutive_
board_failures`, `test_failing_source_does_not_abort_the_batch`).

**Still open:** everything carried from Phase 6 (license confirmation,
Ranking agent-vs-mode decision — next up in Phase 9 itself, Windows
LaTeX docs, Ollama live-server smoke test, real LLM pricing, native
system-prompt support on `LLMProvider`, `populate_by_name=True` audit,
a real eval/cassette harness for agent-level prompt quality). Added:
Greenhouse rate-limit enforcement (config field exists, unused);
agents.md §3's optional LLM-assisted manual-paste normalization
(explicitly trimmed from T7.3, see above).

**Not yet done:** commit/push for this phase — next action. Phase 8
(Job Matching) has not started (this session's single combined request
covers Phases 7–9, but each is still its own commit, matching every
prior phase's convention).

## 2026-08-07 — Phase 8 (Job Matching — Job Matching Agent) complete

**Built, per `tasks.md` T8.1:** `schemas/match.py`'s `MatchScoreExtraction`
(narrower than `MatchScore`, same `CandidateProfileExtraction` pattern
from Phase 5 — excludes `id`/`job_posting_id`/`profile_id`/
`agent_run_id`/`created_at`, fields the model has no basis to fill
in); the prompt file `prompts/library/job_matching/score/1.0.md`
(reconciles `prompts.md` §2's draft, which already existed from the
doc phase — used near-verbatim, extended slightly with an explicit
no-generic-filler instruction); `JobMatchingAgent`. `MatchScore` itself
needed no changes — it was already fully built in Phase 4.

**Two things agents.md §4 asks for that no prior agent needed, both
implemented for real, not stubbed:**
- **Forced `temperature=0.0`** on every `complete_structured` call
  (PRD.md §6 Determinism) — not just relying on the provider's
  default, so a future default change elsewhere can't silently
  un-pin this agent's reproducibility. Verified with a dedicated test
  that inspects what the fake provider actually received, not just
  that the code compiles.
- **A schema-validation-specific retry**, distinct from the shared
  transport-level `call_with_retry` backoff (design.md §11) that
  already lives in each provider adapter: if the LLM's structured
  response fails `MatchScoreExtraction` validation, the agent re-asks
  once with a stricter instruction appended to the same prompt before
  giving up. A second failure propagates the `ValidationError` rather
  than returning a partially-parsed score (agents.md §4 Failure
  handling, "never silently returns a partially-parsed score") — both
  the retry-then-succeed and the give-up-after-two paths have their
  own test, using a small local fake LLM built for this (not the
  shared `FakeLLMProvider`, which always validates successfully by
  construction and can't exercise this path).

**Built the regression suite `testing.md` §4 names as "the canonical
example":** `tests/eval/job_matching/cases/*.yaml`, 10 labeled
(profile, posting, expected score band) pairs — strong match, weak
match (different field entirely), partial match, two seniority-
mismatch directions (over- and under-qualified), a sparse profile, a
close-match-minor-gap, a completely different profession, an
unrealistic-requirement-stacking posting, and an adjacent-field
transferable-skills case. Each case's `matched_requirements`/
`missing_requirements` are checked against a **word-overlap grounding
check** (≥50% of a requirement's significant words must appear in the
posting or profile text) — deliberately not an exact-substring check,
since real rationale text paraphrases ("own our platform architecture"
vs. "platform architecture ownership" shouldn't count as fabrication),
but still catches a requirement sharing *no* words with either source
text. This directly operationalizes phases.md's Phase 8 acceptance
criterion ("rationale references concrete posting/profile text, not
generic filler") as a real, running check, not just a docstring claim.

**Honest limitation, same category as every prior eval suite:** these
10 cases prove the agent's assembly and the grading checks above are
correct given a hand-scripted "golden" response — they do not prove a
*real* LLM would score these cases within the labeled band. Upgrading
requires the same recorded-cassette/live-credential harness flagged as
still-open since Phase 5.

**No architecture.md change needed this phase:** `JobMatchingAgent`
only touches modules already listed as `agents/` dependencies
(`schemas/`, `prompts/`) — checked, found accurate as-is.

**Verified, not assumed:** `ruff check`, `ruff format --check`, `mypy
--strict` (66 source files), full `pytest` (175 passed, up from 156 —
95% coverage), all passing including the 9 agent-level plumbing tests
and the 10-case regression suite.

**Still open:** everything carried from Phase 7 (license confirmation,
Ranking agent-vs-mode decision — next up in Phase 9 itself, Windows
LaTeX docs, Ollama live-server smoke test, real LLM pricing, native
system-prompt support on `LLMProvider`, `populate_by_name=True` audit,
the recorded-cassette eval harness, Greenhouse rate-limit enforcement,
optional LLM-assisted manual-paste normalization).

**Not yet done:** commit/push for this phase — next action. Phase 9
(Ranking) has not started.

## 2026-08-07 — Phase 9 (Ranking) complete

**Resolved a carried-forward open item:** "whether Ranking ends up as
a mode of the Job Matching Agent or a fully separate agent" (open
since the 2026-08-02 entry, phases.md Phase 9's own note flagged it
for implementation time). Confirmed rather than re-litigated: api.md
§3 already specified a plain `Ranker` Protocol / pure function during
the original doc phase, not an `Agent` — consistent with rules.md
§Performance Guidelines ("no agent should require an LLM call for
something a deterministic function can compute"). No new ADR needed;
api.md §3 already *was* the decision, this phase just confirmed
implementation surfaced no reason to revisit it.

**Built, per `tasks.md` T9.1:** `orchestration/ranking.py` — `rank()`
(pure function, no LLM/DB/RunContext), `latest_per_posting()` (collapses
`match_scores`' re-scoring history, database.md §6, to one entry per
posting so a re-scored posting isn't double-counted), `paginate()`
(design.md §2 progressive disclosure, default page size 10 matching
that section's own example); `schemas/match.py`'s `RankedPosting`
(api.md §3); `cli/commands/rank.py` (`jobhunt rank`) and
`.claude/commands/rank.md`, both mirroring Phase 5's `setup`
thin-wrapper pattern (ADR-0004) exactly.

**A real, disclosed deviation from api.md §3's draft, not silently
patched over:** the draft's tie-break was "`posted_at` descending" —
a `JobPosting` field. But `Ranker.rank()` only receives
`list[MatchScore]` (api.md §3's own signature), and joining against
`job_postings` to reach `posted_at` would require DB access inside
`rank()`, contradicting api.md §3's explicit "pure function" design
intent one paragraph earlier in the same section. Used
`MatchScore.created_at` (already on hand) instead — same doc
reconciled with a comment explaining the substitution, not silently
changed. Python's `sorted()` being stable means the core phases.md
acceptance criterion ("same inputs → same order") holds regardless of
which tie-break field is used.

**Verified, not assumed:** `ruff check`, `ruff format --check`
(including a second ruff-version-drift oscillation, same category as
Phase 6's import-order one — local venv ruff 0.16.1 and the
pre-commit-pinned v0.6.9 disagree on multi-line `assert`-with-message
wrapping style; resolved the same way, by treating the pinned
pre-commit hook as authoritative and letting it re-format after the
local run, confirmed stable by re-running `pre-commit run --all-files`
twice back to back with no further changes), `mypy --strict` (68
source files), full `pytest` (191 passed, up from 175 — 96% coverage,
up from 95%), `pre-commit run --all-files` (all 7 hooks green).
Dedicated tests for both Phase 9 acceptance criteria: stability
(`test_rank_is_stable_for_equal_scores`, same input list ranked twice
produces identical order) and pagination
(`test_paginate_returns_correct_slice`,
`test_paginate_default_page_size_is_ten`,
`test_paginate_past_the_end_returns_empty`).

**Honest note, not a new limitation:** `run_setup()` (Phase 5) and now
`run_rank()` both close their SQLAlchemy session in a `finally` block
but never call `engine.dispose()` — a pre-existing pattern, not
something Phase 9 introduced; `test_run_rank_end_to_end_with_scratch_db`
adds one more instance of the same already-accepted
`ResourceWarning: unclosed database` noise seen in every phase's test
run since Phase 4. Not fixed here (out of Phase 9's scope, no doc asks
for connection-pool lifecycle hardening) — flagged below instead.

**No architecture.md change needed this phase:** `ranking.py` only
uses `schemas/` (already an `orchestration/` dependency); the CLI
command only uses already-existing `storage/`/`config/` surfaces.

**Still open:** everything carried from Phase 8 (license confirmation,
Windows LaTeX docs, Ollama live-server smoke test, real LLM pricing,
native system-prompt support on `LLMProvider`, `populate_by_name=True`
audit, the recorded-cassette eval harness, Greenhouse rate-limit
enforcement, optional LLM-assisted manual-paste normalization). Added:
`run_setup()`/`run_rank()`'s missing `engine.dispose()` in their
`finally` blocks (cosmetic — a `ResourceWarning`, not a real leak
within a single CLI-process lifetime — but worth a real fix before
these code paths get reused by more commands).

**Not yet done:** commit/push for this phase — next action, then
Phases 7–9 are all complete. Phase 10 (ATS Optimization) has not
started.
