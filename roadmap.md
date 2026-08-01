# Roadmap — JOB_HUNT

Status: Draft v1.0 · Last updated: 2026-08-02

This is directional, not a commitment with dates — `phases.md` is the
authoritative near-term build order. This doc exists to show where the
architecture is *heading* so v1 decisions don't box in v2.

## 6-Month Horizon (post-v1, Phases 1–18 complete)

- **Career Analytics polish:** richer trend breakdowns (by seniority,
  by company size, by time-to-response), still deterministic
  computation (`agents.md` §11) — no speculative ML modeling.
- **LinkedIn Agent (v1 of it):** profile-optimization suggestions
  grounded in the existing `CandidateProfile` — reuses the `Agent`
  protocol unchanged, per `api.md` §10.
- **Gmail Sync:** a `StatusSignalDetector` that reads reply emails and
  proposes `ApplicationEvent` transitions for user confirmation (never
  auto-applies a status change without review, consistent with
  `PRD.md` §9's human-in-the-loop principle).
- **HTML dashboard v1:** `jobhunt report` — offline, static, generated
  from tracking data (`design.md` §1, `agents.md` §11).
- **Second and third job-source connectors:** validates the plugin
  mechanism (`decisions.md` ADR-0008) against real diversity of source
  shapes, not just the first connector's assumptions.
- **First external contribution:** a community-contributed CV template
  or job-source connector, per `PRD.md` §7's open-source-readiness
  metric.

## 1-Year Horizon

- **Networking / Cold Outreach Agent** and **Salary Negotiation
  Agent** — both have draft prompt sketches already in `prompts.md`;
  promoting them to real phases follows the identical
  design → schema → agent → prompt → registry pattern used for every
  v1 agent.
- **Visa Requirement Agent** — likely needs a small new data source
  (visa/sponsorship information per country/company) — new `sources/`
  connector, not a core rewrite.
- **Academic job-search cluster** (Research Position, Professor Finder,
  Publication Matching, Scholarship agents) — these share a need for a
  "publication/research profile" extension to `CandidateProfile` or a
  parallel `AcademicProfile` schema; worth a dedicated ADR when this
  cluster is actually scheduled, to decide which shape it takes
  (`decisions.md`).
- **Optional lightweight local web view:** *not* a hosted app
  (`decisions.md` ADR-0002 still holds) — a `jobhunt serve --local`
  command that runs a local-only web server serving the same
  `jobhunt report` data interactively, for users who prefer clicking
  over reading a static HTML file. Explicitly not multi-user.
- **Multi-provider maturity:** revisit `decisions.md` ADR-0003 if the
  provider list grows enough that a gateway library (LiteLLM/OpenRouter)
  becomes a better trade than the custom adapter layer — record the
  revisit as a superseding ADR if it happens, don't silently swap.

## Future Features (unscheduled, directional only)

- Per-application "confidence to get an interview" trend calibration
  using the user's own historical outcomes as signal for the Job
  Matching Agent's scoring (an explicit future ADR — this changes
  Matching from stateless-per-posting to informed-by-history, a real
  architectural shift worth deliberate design, not a quiet addition).
- Resume A/B tracking: comparing response rates across different
  `resume_versions`/templates for structurally similar postings.
- Localization / non-English support (`PRD.md` §9 — explicitly out of
  v1 scope, revisit once the core pipeline is stable in English).

## Plugin Ecosystem

- v1 plugin mechanism is in-tree, decorator-based registration
  (`decisions.md` ADR-0008) — sufficient while all agents/sources ship
  in this repo.
- If genuine third-party plugin *packages* emerge (someone maintains
  their own job-source connector as a separate pip package), migrate to
  Python packaging `entry_points`-based discovery that populates the
  same registries (`decisions.md` ADR-0008 alternatives-considered
  note) — additive, not a breaking change to in-tree agents.
- A simple community index (a Markdown or JSON list of known
  third-party templates/connectors, maintained in this repo's `docs/`
  or wiki) is a reasonable first step before anything resembling a
  formal "marketplace" — no need for a hosted registry service at this
  project's scale.

## Enterprise / Multi-User Features (explicitly deferred, not roadmapped for solo timeline)

`PRD.md` §9 places multi-user/hosted SaaS out of scope, and
`decisions.md` ADR-0002 explains why. If a genuine need emerges later
(e.g., a career center wants to run this for many students), the
groundwork already laid (unused `user_id` columns throughout
`database.md`, stateless agent design) makes this a data-layer and
auth-layer migration rather than a rewrite of `jobhunt_core`. This
would warrant a new top-level design pass (its own PRD/architecture
addendum), not a quiet extension of the current single-user docs.
