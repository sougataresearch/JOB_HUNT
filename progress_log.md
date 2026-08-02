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
