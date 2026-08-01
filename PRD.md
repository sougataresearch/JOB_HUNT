# Product Requirements Document — JOB_HUNT

Status: Draft v1.0 · Owner: sougataresearch · Last updated: 2026-08-02

## 1. Problem Statement

Job searching at scale is a repetitive-but-high-stakes information
processing task: for every posting a candidate must (1) find it, (2)
judge whether it's worth applying to, (3) tailor a CV and cover letter to
its specific language and requirements, (4) write a personalized
application email, (5) track the application through its lifecycle, and
(6) prepare for the interview if it converts. Doing this well for even
20 applications a week is beyond what most job seekers can sustain
manually without either quality collapsing (generic, untailored
materials) or volume collapsing (fewer applications than the market
requires).

Existing tools solve slivers of this: job boards aggregate postings but
don't judge fit; resume builders format a CV but don't tailor it per
posting; ATS checkers score keyword overlap but don't rewrite content;
spreadsheets track applications but don't generate anything. No widely
available tool treats the *entire* pipeline — search → fit → tailor →
apply → track → interview — as one system with a shared understanding of
the candidate.

JOB_HUNT exists to close that gap: a single, local-first, AI-agent
pipeline that takes a candidate's CV and career goals as input, and
produces ranked, tailored, submission-ready applications and interview
prep, while keeping a full audit trail of every decision it made.

## 2. Goals

1. **Reduce time-per-application** from tailoring a CV/cover letter by
   hand (typically 30–60 minutes) to a few minutes of human review of an
   AI-generated draft.
2. **Increase application quality** by grounding every generated
   document in the actual posting text and the candidate's actual CV
   content — never inventing experience, never generic boilerplate.
3. **Increase application volume sustainably** by removing the manual
   bottleneck, without sacrificing per-application quality (explicitly
   *not* a spam-blast tool — see Non-Goals in `PRD.md` §9 and
   `rules.md` on anti-spam constraints).
4. **Keep the candidate in control.** Every agent output (ranking,
   tailored CV, cover letter, email, interview answer) is a *draft* the
   human reviews before it is used; the system never auto-submits an
   application on the user's behalf in v1.
5. **Build an architecture that scales to unlimited future agents**
   (LinkedIn, Networking, Salary Negotiation, Visa, Research Position,
   Scholarship, Professor Finder, Publication Matching, etc.) without
   rearchitecting the core — see `architecture.md` §"Plugin Architecture".
6. **Be genuinely useful to one person (the maintainer) first**, then
   generalizable enough to open-source and let others adapt to their own
   CV, region, and job market.

## 3. Target Users

- **Primary (v1):** The maintainer — a single technical user running the
  system locally via Claude Code, applying to software/research/data
  roles internationally (see `references.md`-equivalent context: this is
  a personal tool first).
- **Secondary (post-OSS release):** Individual job seekers comfortable
  installing a Python CLI and running Claude Code locally — technical
  enough to edit YAML config and Markdown/LaTeX templates, but not
  necessarily developers.
- **Tertiary (future, out of v1 scope):** Career centers, bootcamps, or
  research-group PhD/postdoc applicants (via the Research Position /
  Professor Finder / Scholarship agents on the roadmap) — informs
  extensibility requirements now, not feature scope now.

### Explicit non-users (v1)
Recruiters, employers, or ATS vendors — this is a candidate-side tool
only. No feature may require or encourage employer-side data
harvesting.

## 4. Use Cases

1. **Onboarding.** User provides a CV (PDF/DOCX/Markdown) plus career
   goals; system builds a structured candidate profile (skills,
   experience, education, achievements) used by every downstream agent.
2. **Passive sourcing.** User runs a search across configured job boards
   / APIs for a role + location + keyword set; system dedupes and stores
   postings.
3. **Fit scoring.** For each sourced posting, system scores compatibility
   against the candidate profile and explains the score (matched
   requirements, gaps, red flags).
4. **Prioritized shortlist.** User reviews a ranked list (not a raw feed)
   and selects postings to pursue.
5. **ATS-aware tailoring.** For a selected posting, system proposes a
   tailored CV variant emphasizing relevant experience and closing
   keyword gaps, without fabricating experience.
6. **Cover letter + email generation.** System drafts a cover letter and
   a submission email in the user's voice, referencing specifics from
   the posting.
7. **Human review gate.** User edits/approves the generated package
   before anything is sent or exported.
8. **Application tracking.** System records what was submitted, when,
   with which CV/cover-letter version, and its current status
   (applied → screening → interview → offer/rejected).
9. **Interview preparation.** For an application marked "interview
   scheduled," system generates likely questions (technical + company +
   role-specific) and talking points grounded in the tailored CV and the
   posting.
10. **Retrospective analytics.** User reviews aggregate stats (response
    rate by role type, by seniority, by source) to adjust strategy.
11. **Skill-gap driven upskilling (future agent).** System identifies
    recurring unmet requirements across rejected/low-scored postings and
    suggests learning targets.

## 5. Features

### 5.1 Must-have (v1 scope — see `phases.md` Phases 1–12)
- CV ingestion & structured profile extraction (PDF/DOCX/Markdown input)
- Skill-gap analysis against a target role/profile
- Multi-source job search with deduplication
- Job–candidate compatibility scoring with human-readable rationale
- Ranking of sourced postings
- ATS keyword-gap analysis
- CV customization per posting (LaTeX-rendered, ATS-verified PDF output)
- Cover letter generation per posting
- Application email drafting
- Application tracking (status lifecycle, CSV/HTML export)
- Interview question & talking-point preparation
- Multi-provider LLM support (Anthropic, OpenAI, local via Ollama)
- Full local persistence (SQLite + filesystem); no data leaves the
  machine except to the configured LLM provider and job-source APIs

### 5.2 Should-have (near-term post-v1 — see `roadmap.md`)
- Career analytics agent (response-rate trends, source effectiveness)
- LinkedIn profile optimization agent
- Gmail sync for automatic status detection from reply emails
- HTML offline dashboard generated from tracking data
- Additional job-board/API integrations via the plugin system

### 5.3 Could-have (roadmap, not committed)
- Networking / cold-outreach agent
- Salary negotiation agent
- Visa requirement agent
- Research Position / Professor Finder / Publication Matching agents
  (for academic job seekers)
- Scholarship agent

### 5.4 Won't-have (v1) — see §9 Out of Scope

## 6. Non-Functional Requirements

- **Local-first & offline-capable where possible.** Core data (profile,
  jobs, applications) lives on disk; only LLM calls and job-source
  lookups require network access. See `architecture.md` §Technology
  Choices and `decisions.md` ADR-0002.
- **Provider-agnostic AI layer.** No agent may hard-code a specific LLM
  vendor's SDK; all calls go through the `LLMProvider` interface
  (`api.md` §LLM API). See `decisions.md` ADR-0003.
- **Determinism where it matters.** Ranking/scoring must be reproducible
  given the same inputs and model+temperature config, to support
  regression testing (`testing.md` §AI Evaluation).
- **Extensibility.** Adding a new agent must require: one new module, one
  registry entry, one prompt file, and (optionally) one new Claude Code
  command — never a change to existing agent code. See `architecture.md`
  §Plugin Architecture and `rules.md` Rule on extension points.
- **Auditability.** Every agent invocation (input, prompt version, model,
  output, cost, latency) is logged so any generated document is
  traceable to exactly what produced it (`design.md` §Logging Strategy).
- **Human-in-the-loop by default.** No agent output that leaves the
  system (email send, application submission) fires without explicit
  user confirmation in v1.
- **Cost-boundedness.** Every LLM-calling agent respects configured
  per-run and per-day token/cost ceilings (`config.md` §Rate Limits).
- **Portability.** Runs on Windows, macOS, and Linux with Python 3.11+
  and a LaTeX distribution; no OS-specific code paths in core logic.
- **Security.** Secrets never committed, never logged; see `rules.md`
  §Secrets Management and `design.md` §Security Considerations.
- **Testability.** Every agent is unit-testable without live network/LLM
  calls via recorded fixtures (`testing.md` §Prompt Testing).

## 7. Success Metrics

### Product-level (personal use, v1)
- Time from "found a posting" to "submission-ready package" ≤ 10 minutes
  of active user time (review + edit), down from ~45–60 minutes manual.
- ≥ 90% of generated CV/cover-letter content is used with only minor
  edits (not full rewrites) — tracked via a simple accept/edit/reject
  flag at the review gate.
- Zero fabricated experience/claims shipped in a submitted document
  (hard requirement, checked by the ATS/verification loop plus manual
  review — see `rules.md` AI Coding Rule on never inventing content).
- Application-tracking data complete enough to compute response rate,
  interview rate, and offer rate without manual reconciliation.

### System-level (engineering)
- New agent added in ≤ 1 day of engineering time once its prompt is
  designed (validates the plugin architecture goal).
- ≥ 80% unit test coverage on core (non-LLM) logic; all agents have at
  least golden-file prompt tests (`testing.md`).
- No secret or PII ever appears in committed source or logs (verified by
  CI secret-scanning, see `rules.md` §Git Workflow).

### Open-source-readiness metrics (post-v1)
- A new contributor can set up the dev environment and run the test
  suite following `README.md`/`rules.md` alone, with no undocumented
  steps.
- At least one job-board integration and one CV template contributed by
  someone other than the maintainer within 6 months of public release
  (`roadmap.md`).

## 8. Future Vision

JOB_HUNT's long-term shape is a **general-purpose career-agent
platform**: the same plugin architecture that runs the core job-search
pipeline should be able to host agents for academic job hunting
(professor/PhD/postdoc search, publication matching, scholarship
discovery), professional networking, salary negotiation, and
visa/relocation logistics — each as an independently maintainable module
against the same candidate-profile and application-tracking core. The
system should eventually support:

- A plugin marketplace-style registry (local directory of community
  agents/portals/templates, no central server required — see
  `roadmap.md` §Plugin Ecosystem).
- Optional multi-user / hosted mode for career centers or coaching
  services (explicitly deferred — see §9).
- A richer analytics agent that treats the user's own application
  history as training signal for its own ranking calibration.

## 9. Out of Scope (v1)

- **Auto-submission of applications.** The system drafts; the human
  submits. No agent fills out and clicks "Submit" on a third-party job
  portal in v1.
- **Mass/spam applications.** No feature exists to blast the same
  materials to many postings without per-posting tailoring; this is a
  quality tool, not a volume-spam tool (see `rules.md` anti-abuse rule).
- **Multi-user / hosted SaaS.** v1 is single-user, local-first (see
  Deployment Model decision, `decisions.md` ADR-0002). Multi-tenant
  hosting is future roadmap only.
- **Scraping sites that prohibit it in their Terms of Service.** Only
  sources with an API, an explicit scraping allowance, or manual
  paste/import are supported (see `rules.md` §Security/Compliance).
- **Building a proprietary job board or aggregator for others to use.**
  JOB_HUNT consumes job data; it does not become a job board itself.
- **Full ATS reverse-engineering per company.** ATS optimization targets
  general parsing correctness (text extraction, standard section
  headers, keyword presence) — not modeling any specific vendor's
  proprietary ranking algorithm.
- **Non-English localization** in v1 (structure should not preclude it
  later — see `roadmap.md` — but no i18n work is scoped now).
