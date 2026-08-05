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
