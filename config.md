# Configuration Strategy — JOB_HUNT

Status: Draft v1.0 · Last updated: 2026-08-02

Full layering rationale in `design.md` §8. This doc is the concrete
reference: file locations, key names, and defaults.

## Layering (highest precedence last)

1. `config/*.yaml` — committed defaults, no secrets.
2. `config/local.yaml` — gitignored, personal overrides (e.g., which
   sources you've enabled, your preferred model tier).
3. Environment variables / `.env` — secrets and CI/deploy overrides,
   always win.

All three are merged into one typed `Settings` object
(`pydantic-settings`) at process start; nothing reads `os.environ`
directly outside `config/settings.py` (`rules.md`).

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | if Anthropic enabled | Claude API access |
| `OPENAI_API_KEY` | if OpenAI enabled | OpenAI API access |
| `OLLAMA_HOST` | if local provider enabled | default `http://localhost:11434` |
| `JOBHUNT_DATA_DIR` | no | override `data/` location, default `./data` |
| `JOBHUNT_LOG_LEVEL` | no | default `INFO` |
| `JOBHUNT_LOG_LLM_BODIES` | no | `1` to opt into DEBUG-level prompt/response body logging (`design.md` §9) — off by default |
| `JOBHUNT_ENV` | no | `dev` \| `test` \| `prod`-equivalent (local machine profile), default `dev` |

`.env.example` ships with every key listed, placeholder values only
(`rules.md` §Secrets Management).

## Feature Flags — `config/agents.yaml`

```yaml
agents:
  resume_analysis:   { enabled: true,  provider: anthropic, model: claude-sonnet-5 }
  skill_gap:         { enabled: true,  provider: anthropic, model: claude-sonnet-5 }
  job_search:        { enabled: true }
  job_matching:      { enabled: true,  provider: anthropic, model: claude-sonnet-5 }
  ats_optimization:  { enabled: true,  provider: anthropic, model: claude-haiku-4-5 }
  resume_customization: { enabled: true, provider: anthropic, model: claude-sonnet-5 }
  cover_letter:      { enabled: true,  provider: anthropic, model: claude-sonnet-5 }
  email_generation:  { enabled: true,  provider: anthropic, model: claude-haiku-4-5 }
  application_tracking: { enabled: true }   # no LLM
  interview_prep:    { enabled: true,  provider: anthropic, model: claude-sonnet-5 }
  career_analytics:  { enabled: true,  provider: anthropic, model: claude-haiku-4-5 }
  # future, disabled until their phase lands (roadmap.md):
  linkedin:          { enabled: false }
  networking:        { enabled: false }
  salary_negotiation: { enabled: false }
```

Model tiering rationale: cheaper/faster models (`claude-haiku-4-5`) for
lower-judgment tasks (keyword classification, email formatting,
narrative summaries); stronger models (`claude-sonnet-5`) for tasks
requiring nuanced judgment (matching rationale, resume tailoring,
interview grounding). Per-agent override in `config/local.yaml` is
always allowed.

## Provider Settings — `config/llm.yaml`

```yaml
llm:
  default_provider: anthropic
  providers:
    anthropic:
      base_model: claude-sonnet-5
      timeout_s: 60
      max_retries: 3
    openai:
      base_model: gpt-5
      timeout_s: 60
      max_retries: 3
    ollama:
      base_model: llama3
      timeout_s: 120
      max_retries: 2
  limits:
    per_run_max_cost_usd: 2.00
    per_day_max_cost_usd: 20.00
    per_agent_max_calls_per_run:
      job_matching: 200        # e.g., scoring a large batch
```

## Rate Limits & Cost Ceilings

`limits` (above) lives nested under `llm:` in `config/llm.yaml` — it's
LLM-call/cost-related, not source-fetch-related, so it belongs beside
the provider settings rather than in its own file (`tasks.md` T2.1
only names `llm.yaml`/`agents.yaml`/`sources.yaml`, no separate
`limits.yaml`). Job-source-specific rate limiting is *not* duplicated
here — it's the per-source `rate_limit_per_min` field already in
`config/sources.yaml` (§Source Configuration, below); a single global
default would only conflict with those per-source values.

An agent (or the orchestrator, on its behalf) that would exceed
`per_run_max_cost_usd`/`per_day_max_cost_usd` stops and raises a
`BudgetExceededError` with a `.remedy` telling the user how to raise
the ceiling — it never silently continues spending (`design.md` §6
Non-Functional Requirements, `rules.md` §Performance Guidelines).

## Timeouts

- LLM calls: `timeout_s` per provider (above), enforced client-side in
  addition to whatever the SDK defaults to.
- Job source fetches: default 15s per request, configurable per source
  in `config/sources.yaml`.
- LaTeX compilation: 30s ceiling per document; a hang beyond that is
  treated as a `RenderError`, not silently killed without reporting.

## Caching

- **LLM response caching:** none in v1 beyond provider-side prompt
  caching (Anthropic's native prompt caching is used automatically for
  the static portions of prompts — system instructions, guardrail
  block — where the SDK exposes it; no separate application-level
  cache layer is built, to avoid a second source of staleness for a
  single-user tool with low call-volume).
- **Job source response caching:** raw fetch responses are persisted
  under `data/raw/` regardless (`database.md` §5
  `raw_content_path`), which functions as a de facto cache/audit copy —
  no separate TTL-based cache needed at this scale.

## Model Selection

Configured per-agent in `config/agents.yaml` (above), with a global
`default_provider`/`base_model` fallback in `config/llm.yaml`. Switching
a provider or model requires no code change — only a config edit —
which is the concrete payoff of `decisions.md` ADR-0003.

## LLM Providers Supported (v1)

Anthropic, OpenAI, Ollama (local) — see `api.md` §5 and
`decisions.md` ADR-0003 for the interface contract and reasoning.
Adding a fourth provider is a `config.md`-only change plus one new
adapter file (`architecture.md` §6), never a change to agent code.

## Source Configuration — `config/sources.yaml`

```yaml
sources:
  greenhouse:      { enabled: true,  rate_limit_per_min: 30 }
  manual_import:   { enabled: true }
  # additional sources added per phases.md Phase 7 / roadmap.md
```

## Config Validation Rules

- `Settings` load fails fast (at process start, not mid-run) if a
  required secret for an *enabled* agent/provider is missing.
- Disabling a provider that an enabled agent depends on is a validation
  error at load time, not a runtime surprise mid-pipeline.
- Every new config key introduced by a code change must be documented
  here in the same PR (`rules.md` §Configuration Rules).
