## What this changes and why

## Checklist

- [ ] `ruff check . && ruff format --check .` pass
- [ ] `mypy` passes
- [ ] `pytest --cov-fail-under=80` passes
- [ ] `pre-commit run --all-files` passes
- [ ] No unit test makes a live network or LLM call
- [ ] New/changed agent has an `agents.md` entry and versioned prompt
      (if it calls an LLM), documented in `prompts.md`
- [ ] New/changed schema crossing a module boundary is reflected in
      `database.md`/`api.md`
- [ ] A prompt handling untrusted content (posting text, scraped HTML,
      a CV) is delimited with `<untrusted_content>` and instructed to
      ignore embedded instructions — covered by
      `tests/security/test_prompt_injection_guardrails.py`
- [ ] Schema change to a SQLAlchemy model includes an Alembic migration
- [ ] No secrets, API keys, or real personal data anywhere in the diff
- [ ] Docs (`README.md`, `docs/quickstart.md`) updated if setup steps
      or the CLI surface changed

## Anything reviewers should pay special attention to
