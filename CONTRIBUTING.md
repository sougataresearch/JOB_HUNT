# Contributing to JOB_HUNT

Thanks for considering a contribution. This project is a personal tool
first, open-source project second (`PRD.md` §3) — contributions that
make it more broadly useful (new job-source connectors, CV/cover-letter
templates, provider adapters) are especially welcome; changes that
narrow it to one person's specific workflow at the expense of everyone
else's usually aren't the right fit.

## Before you start

1. Read [`docs/quickstart.md`](docs/quickstart.md) and get `pytest`
   passing locally first.
2. Skim [`rules.md`](rules.md) — it's binding, not advisory. The most
   important rule: **never let a generated document fabricate a skill,
   employer, or achievement not present in the candidate's real
   profile** (AI Coding Rule 1). Everything else is negotiable in a
   PR discussion; that one isn't.
3. Check [`phases.md`](phases.md) and [`progress_log.md`](progress_log.md)
   for what's already done and what's explicitly still open — a PR
   that duplicates in-flight work or reopens a settled ADR
   (`decisions.md`) without new evidence will just cost you a round
   trip.

## Making a change

- Branch off `main`: `feat/<slug>`, `fix/<slug>`, `docs/<slug>`, or
  `chore/<slug>` (`rules.md` §Git Workflow).
- Follow the existing patterns: one agent per file under
  `src/jobhunt_core/agents/`, a matching test module under `tests/`
  mirroring the same path, a prompt template under
  `prompts/library/<domain>/<name>/<version>.md` (never inlined as a
  Python string) if your change adds or edits an LLM call.
- Run before opening a PR:
  ```bash
  ruff check . && ruff format --check .
  mypy
  pytest --cov-fail-under=80
  pre-commit run --all-files
  ```
- New/changed schemas that cross a module boundary belong in
  `schemas/` and should be reflected in `database.md`/`api.md`. New
  agents need an `agents.md` entry and a versioned prompt (if any)
  documented in `prompts.md` — before or alongside the code, not as an
  afterthought (`rules.md` §Documentation Rules).
- Every prompt that ingests untrusted content (job posting text,
  scraped HTML, a user-uploaded CV) must wrap it in
  `<untrusted_content>` tags and explicitly instruct the model to
  ignore any embedded instructions within it
  (`tests/security/test_prompt_injection_guardrails.py` enforces this
  structurally for every prompt in the library — a new prompt handling
  untrusted content needs a corresponding entry there).
- No unit test may make a live network or LLM call — use the shared
  `FakeLLMProvider` (`tests/conftest.py`) or a small scripted fake for
  multi-call sequences (see `tests/agents/test_resume_customization_agent.py`
  for the pattern). Real LaTeX compiles in tests are fine and expected
  for document-rendering agents.

## Commit style

Conventional Commits (`feat(agents): add LinkedIn source connector`,
`fix(storage): correct Alembic downgrade for X`,
`docs(readme): clarify LaTeX setup`). Explain *why* in the body, not
just what — the diff already shows what changed.

## Opening a PR

- CI (lint, type-check, tests + coverage gate, secret scan,
  dependency audit) must be green.
- Describe what you tested manually, if anything, beyond the
  automated suite (e.g., a real LLM call against a live API key,
  which CI itself never does).
- If your change touches a security-relevant area (prompt handling of
  untrusted content, secrets, third-party credentials), say so
  explicitly in the PR description — see `rules.md` §Security Rules.

## Questions

Open a [GitHub issue](https://github.com/sougataresearch/JOB_HUNT/issues)
using the appropriate template. For anything not covered by the
templates, a plain issue describing what you're trying to do is fine.
