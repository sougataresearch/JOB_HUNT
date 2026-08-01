# JOB_HUNT

**An autonomous, local-first AI career assistant.** JOB_HUNT searches jobs
across multiple sources, analyzes your CV, scores fit, customizes your
resume, writes cover letters and application emails, preps you for
interviews, and tracks every application — all running on your own
machine, driven through [Claude Code](https://claude.com/claude-code)
commands, with no mandatory cloud backend beyond your chosen LLM API.

This repository is currently in the **architecture and documentation
phase**. No application code has been written yet — see
[`phases.md`](phases.md) and [`implementation_order.md`](implementation_order.md)
for what gets built, and in what order.

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

Architecture design in progress. See [`progress_log.md`](progress_log.md)
for the latest entry before starting any substantive work.

## License

MIT (proposed — see [`decisions.md`](decisions.md) ADR-0009). Not yet
applied to a `LICENSE` file pending final confirmation before the first
public push.
