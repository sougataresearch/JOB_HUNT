# JOB_HUNT

**An autonomous, local-first AI career assistant.** JOB_HUNT searches jobs
across multiple sources, analyzes your CV, scores fit, customizes your
resume, writes cover letters and application emails, preps you for
interviews, and tracks every application — all running on your own
machine, driven through [Claude Code](https://claude.com/claude-code)
commands, with no mandatory cloud backend beyond your chosen LLM API.

**Phases 1–17 of 18 are complete** — eleven real, tested agents
(`resume_analysis`, `skill_gap`, `job_search`, `job_matching`,
`ats_optimization`, `resume_customization`, `cover_letter`,
`email_generation`, `application_tracking`, `interview_prep`,
`career_analytics`), a working CLI (`setup`, `rank`, `outcome`,
`interview`, `report`), a compiling LaTeX rendering pipeline, an
offline HTML analytics dashboard, an end-to-end fixture pipeline test,
and CI gates (lint, types, tests, ≥80% coverage, `pip-audit`,
secret scanning). See [`phases.md`](phases.md) and
[`implementation_order.md`](implementation_order.md) for what's built
and what's left, and [`progress_log.md`](progress_log.md) for the
detailed, dated build history.

## Why this exists

Manually tailoring a CV and cover letter for every job posting doesn't
scale past a handful of applications. JOB_HUNT turns the repetitive parts
of a job search — sourcing postings, judging fit, tailoring documents,
prepping for interviews, tracking outcomes — into a pipeline of small,
auditable AI agents you can inspect, override, and extend.

## How it's organized (read in this order)

| Doc | Purpose |
|---|---|
| [`PRD.md`](PRD.md) | Problem, goals, users, features, success metrics — the *what* and *why* |
| [`architecture.md`](architecture.md) | System architecture, agent model, data/communication flow |
| [`design.md`](design.md) | UX philosophy, DB design, conventions, error handling, security |
| [`decisions.md`](decisions.md) | ADRs — architectural decisions and the reasoning behind them |
| [`phases.md`](phases.md) | Development milestones, in dependency order |
| [`rules.md`](rules.md) | Binding coding, git, testing, and security rules |
| [`memory.md`](memory.md) | What an AI coding agent must remember about this project |
| [`tasks.md`](tasks.md) | Phase-by-phase implementation task breakdown |
| [`api.md`](api.md) | Internal interface contracts between modules |
| [`database.md`](database.md) | Data models and schema |
| [`agents.md`](agents.md) | Per-agent design specs (purpose, I/O, prompts, failure handling) |
| [`prompts.md`](prompts.md) | The prompt library |
| [`config.md`](config.md) | Configuration, secrets, feature flags, provider settings |
| [`testing.md`](testing.md) | Testing strategy incl. AI evaluation and regression testing |
| [`roadmap.md`](roadmap.md) | 6-month / 1-year roadmap, plugin ecosystem |
| [`folder_structure.md`](folder_structure.md) | The production folder layout |
| [`implementation_order.md`](implementation_order.md) | The exact build order, dependency by dependency |
| [`final_review.md`](final_review.md) | Self-critique of this architecture — weaknesses and mitigations |
| [`progress_log.md`](progress_log.md) | Dated log of decisions and open items |

## Status

**Phases 1–17 complete** (Foundation through Testing & Quality
Hardening). Still open: Deployment & Open-Source Release (Phase 18) —
see [`phases.md`](phases.md) for the full roadmap and
[`memory.md`](memory.md) for a current-state snapshot. Check
[`progress_log.md`](progress_log.md) for the latest dated entry before
starting any substantive work — it carries forward every known open
item and honest limitation (e.g. no real-LLM eval harness yet; every
existing eval test proves agent plumbing against a scripted response,
not real model quality).

### What works today

- `python -m cli.main setup <cv_file>` — parse a CV into a
  `CandidateProfile`.
- `python -m cli.main rank --page 1` — a ranked, paginated shortlist of
  scored postings.
- `python -m cli.main outcome <job_posting_id> <status>` — record an
  application status transition.
- `python -m cli.main interview <job_posting_id> <interview_type>` —
  generate grounded interview prep questions once an application is
  `interview_scheduled`.
- `python -m cli.main report` — write an offline HTML dashboard of
  response/interview/offer rates by role and source.
- Every agent above `setup`/`rank`/`outcome`/`interview`/`report` is
  directly callable via its `Agent.run(input, ctx)` interface
  (`api.md` §0); `tests/e2e/test_full_apply_pipeline.py` chains the
  full Resume Analysis → Application Tracking sequence end to end
  against fixture data.

## License

MIT (proposed — see [`decisions.md`](decisions.md) ADR-0009). Not yet
applied to a `LICENSE` file pending final confirmation before the first
public push.
