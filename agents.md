# AI Agent Designs — JOB_HUNT

Status: Draft v1.0 · Last updated: 2026-08-02

Every agent below implements the common `Agent` protocol
(`api.md` §0). "Tools" means external capabilities the agent's
implementation calls (not necessarily LLM tool-use in the API sense —
some are plain function calls). "Memory" means what persisted state it
reads/writes via `RunContext.repos`. All prompt templates referenced
live in [`prompts.md`](prompts.md).

---

## 1. Resume Analysis Agent

- **Purpose:** Convert a raw CV file into a structured, reusable
  `CandidateProfile`.
- **Responsibilities:** Parse file → extract skills/experience/
  education/certifications → flag low-confidence/ambiguous fields
  explicitly rather than guessing.
- **Inputs:** `ParsedDocument` (`api.md` §1) + optional user-supplied
  hints (target role, seniority).
- **Outputs:** `CandidateProfile` (`database.md` §2).
- **Tools:** `CVParser` implementations (PDF/DOCX/Markdown).
- **Memory:** Writes `candidate_profiles`; reads none (first agent in
  the pipeline).
- **Failure handling:** Unparseable file → `AgentInputError` with a
  `.remedy` suggesting re-export as PDF; partially parseable file →
  succeeds with explicit `null`/low-confidence fields, never a guess
  presented as fact (`rules.md` AI Coding Rule 1).
- **Retry logic:** No LLM retry needed beyond the shared `llm/retry.py`
  policy (`design.md` §11) for transient provider errors; parsing
  itself is deterministic, not retried.
- **Prompt template:** `prompts/library/resume_analysis/extract_profile.md`.
- **Metrics:** Field-extraction accuracy vs. hand-labeled fixtures
  (`testing.md` §AI Evaluation); % of fields flagged low-confidence.
- **Communication protocol:** Output persisted via `ProfileRepo`; every
  downstream agent reads the *active* profile through the same
  repository, never a copy passed hand-to-hand in memory.

---

## 2. Skill Gap Agent

- **Purpose:** Identify skills/experience the candidate is missing
  relative to a target role or market.
- **Responsibilities:** Compare `CandidateProfile` against either a
  user-specified target role description or an aggregate of recently
  sourced postings; produce a prioritized gap list with rationale.
- **Inputs:** `CandidateProfile`, target role text or `list[JobPosting]`.
- **Outputs:** `SkillGapReport` (gaps, each with evidence/absence
  citation, and a suggested priority).
- **Tools:** None beyond the LLM call.
- **Memory:** Reads `candidate_profiles`, `job_postings`; writes nothing
  persisted by default in v1 (report is ephemeral/CLI-output) — may
  gain a `skill_gap_reports` table if the Career Analytics Agent needs
  historical trend data (flag as a future schema addition, not built
  speculatively now per `rules.md` §Refactoring Rules no-speculative-
  abstraction).
- **Failure handling:** Empty/too-sparse profile → returns a report
  stating insufficient data, does not fabricate gaps.
- **Retry logic:** Shared LLM retry policy only.
- **Prompt template:** `prompts/library/skill_gap/analyze.md`.
- **Metrics:** Gap relevance judged via golden-file comparison against
  hand-curated expected gaps for fixture profiles.
- **Communication protocol:** Stateless request/response via
  Orchestrator; no persistence dependency on other agents' output
  beyond reading `CandidateProfile`.

---

## 3. Job Search Agent

- **Purpose:** Source job postings from configured channels and dedupe.
- **Responsibilities:** Query every enabled `JobSource`; normalize
  `RawPosting → JobPosting`; dedupe (exact key + fuzzy hash,
  `database.md` §5); isolate per-source failures.
- **Inputs:** `SearchQuery` (`api.md` §2).
- **Outputs:** `list[JobPosting]` (new rows only — already-seen
  postings are recognized, not re-inserted).
- **Tools:** Registered `JobSource` connectors (`sources/`).
- **Memory:** Writes `job_postings`, `search_runs`; reads
  `job_postings` for dedup lookups.
- **Failure handling:** Per-source `SourceFetchError` is caught,
  logged, and the source is skipped for the remainder of the run after
  N consecutive failures (circuit breaker) — the batch continues
  (`design.md` §10).
- **Retry logic:** Shared backoff policy per source fetch, independent
  circuit breaker state per source per run.
- **Prompt template:** None required for sourcing itself (deterministic
  connector logic); an optional LLM-assisted normalization step may use
  `prompts/library/job_search/normalize_posting.md` for messy/manual-
  paste input specifically.
- **Metrics:** Postings found, new vs. duplicate ratio, per-source
  failure rate (surfaced in `search_runs`).
- **Communication protocol:** Downstream agents (Matching, ATS) read
  `job_postings` via `JobRepo`, never receive postings hand-passed from
  this agent directly.

---

## 4. Job Matching Agent

- **Purpose:** Score compatibility between the candidate and a specific
  posting, with an explainable rationale.
- **Responsibilities:** Compare `CandidateProfile` against
  `JobPosting.normalized_description`; identify matched/missing
  requirements and red flags (e.g., mismatched seniority, unstated
  visa sponsorship requirement conflicting with candidate needs).
- **Inputs:** `CandidateProfile`, `JobPosting`.
- **Outputs:** `MatchScore` (`database.md` §6).
- **Tools:** None beyond the LLM call.
- **Memory:** Reads `candidate_profiles`, `job_postings`; writes
  `match_scores`.
- **Failure handling:** LLM output failing schema validation →
  `AgentInputError`-equivalent output error, retried once with a
  stricter structured-output call before surfacing to the user (never
  silently returns a partially-parsed score).
- **Retry logic:** Shared LLM retry + one structured-output-specific
  re-ask on schema validation failure.
- **Prompt template:** `prompts/library/job_matching/score.md`.
- **Metrics:** Reproducibility at temperature=0 (`PRD.md` §6); tracked
  against a fixed regression suite of labeled (profile, posting,
  expected score band) pairs across prompt version changes
  (`testing.md`).
- **Communication protocol:** Output read by Ranking (`api.md` §3), ATS
  Optimization, and Resume Customization agents via `MatchRepo`.

---

## 5. ATS Optimization Agent

- **Purpose:** Identify keyword/formatting gaps that would hurt
  automated resume parsing for a specific posting.
- **Responsibilities:** Diff posting language against
  `CandidateProfile`; classify each gap as *supported* (real experience
  exists, just needs surfacing/rewording) or *unsupported* (no
  underlying experience — must not be fabricated).
- **Inputs:** `CandidateProfile`, `JobPosting`.
- **Outputs:** `ATSReport` (`database.md` §7).
- **Tools:** Deterministic keyword/embedding-similarity matching where
  possible (`rules.md` §Performance Guidelines — LLM reserved for
  judgment calls like "is this gap actually supported by experience
  worded differently").
- **Memory:** Reads `candidate_profiles`, `job_postings`; writes
  `ats_reports`.
- **Failure handling:** If the underlying keyword-extraction step fails
  (e.g., empty posting text), returns an explicit low-confidence report
  rather than a fabricated one.
- **Retry logic:** Shared LLM retry policy for the judgment sub-step
  only; deterministic matching is not retried (not a transient
  operation).
- **Prompt template:** `prompts/library/ats/analyze.md`.
- **Metrics:** Precision/recall of gap classification against
  hand-labeled fixture cases.
- **Communication protocol:** Output consumed directly by Resume
  Customization Agent as a required input (`architecture.md` §3.1).

---

## 6. Resume Customization Agent

- **Purpose:** Produce a tailored, compiled, ATS-verified CV PDF for a
  specific posting.
- **Responsibilities:** Select relevant experience/bullets
  (relevance-weighted trimming, prioritizing posting-relevant content
  over strict chronological order — pattern validated in
  MadsLorentzen/ai-job-search); render via LaTeX template; run a
  drafter→reviewer critique pass; verify PDF text extraction.
- **Inputs:** `CandidateProfile`, `JobPosting`, `ATSReport`.
- **Outputs:** `ResumeVersion` (`database.md` §3) — LaTeX source + PDF
  + verification result.
- **Tools:** `DocumentRenderer` (LaTeX/Jinja2, `api.md`/`decisions.md`
  ADR-0007), `pdftotext` verification.
- **Memory:** Reads `candidate_profiles`, `job_postings`, `ats_reports`,
  `templates`; writes `resume_versions`.
- **Failure handling:** LaTeX compile failure surfaces the actual log
  to the user (`design.md` §10); reviewer pass catching a fabrication
  or an ATS-breaking format issue triggers exactly one redraft attempt
  before surfacing to the user (`design.md` §11).
- **Retry logic:** One automatic redraft on reviewer rejection; one
  automatic recompile attempt after a known-fixable escaping issue;
  no further automatic retries.
- **Prompt template:** `prompts/library/resume_customization/draft.md`
  and `.../review.md` (separate, fresh-context reviewer prompt).
- **Metrics:** ATS verification pass rate; reviewer rejection rate per
  prompt version (regression signal if it spikes after a prompt edit).
- **Communication protocol:** Output consumed by Cover Letter Agent
  (for consistency) and Application Tracking Agent (as the
  application's attached resume).

---

## 7. Cover Letter Agent

- **Purpose:** Draft a tailored cover letter for a specific posting.
- **Responsibilities:** Reference concrete posting details; stay
  consistent with the tailored resume's claims; render via LaTeX.
- **Inputs:** `CandidateProfile`, `JobPosting`, `ResumeVersion`.
- **Outputs:** `CoverLetter` (`database.md` §8).
- **Tools:** `DocumentRenderer` (shared with Resume Customization).
- **Memory:** Reads `candidate_profiles`, `job_postings`,
  `resume_versions`; writes `cover_letters`.
- **Failure handling:** Same LaTeX compile-failure handling as Resume
  Customization Agent (shared renderer).
- **Retry logic:** Same pattern as Resume Customization Agent (shared
  drafter→reviewer + recompile policy).
- **Prompt template:** `prompts/library/cover_letter/draft.md`.
- **Metrics:** Keyword-presence eval (references ≥N concrete posting
  details); cross-check eval (no contradiction with resume content).
- **Communication protocol:** Output consumed by Email Generation
  Agent as an attachment reference.

---

## 8. Email Generation Agent

- **Purpose:** Draft the application submission email.
- **Responsibilities:** Compose a concise, professional email
  referencing the attached tailored resume and cover letter; never
  auto-send.
- **Inputs:** `JobPosting`, `ResumeVersion`, `CoverLetter`.
- **Outputs:** `EmailDraft` (`api.md` §6) — status always `"draft"`.
- **Tools:** None beyond the LLM call.
- **Memory:** Reads `job_postings`, `resume_versions`, `cover_letters`;
  writes nothing persisted independently in v1 (the draft is surfaced
  at review time and, once approved, its content is folded into the
  `applications` row's audit trail via the linked `agent_run_id`).
- **Failure handling:** Missing recipient information → `to: null`
  with an explicit warning, never a guessed email address.
- **Retry logic:** Shared LLM retry policy only.
- **Prompt template:** `prompts/library/email/draft.md`.
- **Metrics:** Attachment-reference correctness (automated check, not
  an LLM judgment); recipient-null rate (signals when source data is
  incomplete).
- **Communication protocol:** Terminal output of the "generate package"
  stage — presented to the user for the review gate before
  `Application Tracking Agent` records anything (`design.md` §2).

---

## 9. Application Tracking Agent

- **Purpose:** Persist and manage the lifecycle of every application.
- **Responsibilities:** Create/update `Application` rows; append
  `ApplicationEvent` on every status change; export CSV/report data.
- **Inputs:** Approved package (resume/cover-letter/email references),
  or a status-update command (`status`, optional `note`).
- **Outputs:** `Application` row + `ApplicationEvent` row.
- **Tools:** CSV writer; (future) Gmail sync signal detector
  (`roadmap.md`).
- **Memory:** Writes `applications`, `application_events`; reads
  `job_postings`, `resume_versions`, `cover_letters`.
- **Failure handling:** Duplicate application attempt (same
  `job_posting_id`) → returns the existing record rather than erroring
  or duplicating (`design.md` §2 idempotent re-runs).
- **Retry logic:** No LLM call in the core path (pure data operation);
  no retry needed beyond standard DB-transaction retry-on-lock (SQLite
  busy-timeout, not exponential backoff).
- **Prompt template:** None (deterministic agent — included here for
  completeness of the pipeline, not because it calls an LLM).
- **Metrics:** Data completeness (no application missing a required
  status history entry); CSV export correctness vs. fixture aggregates.
- **Communication protocol:** The system of record every other
  tracking-adjacent agent (Interview Prep, Career Analytics) reads
  from.

---

## 10. Interview Preparation Agent

- **Purpose:** Generate likely interview questions and grounded talking
  points once an application reaches `interview_scheduled`.
- **Responsibilities:** Combine posting content, tailored resume, and
  interview type to produce categorized questions with talking points
  traceable to specific resume bullets or posting lines.
- **Inputs:** `Application` (status-triggered), `JobPosting`,
  `ResumeVersion`, `MatchScore`.
- **Outputs:** `InterviewPrepPack` (`database.md` §12,
  `interview_questions` rows).
- **Tools:** None beyond the LLM call.
- **Memory:** Reads `applications`, `job_postings`, `resume_versions`,
  `match_scores`; writes `interviews`, `interview_questions`.
- **Failure handling:** Insufficient grounding data (e.g., posting text
  very short) → generates general-category questions only, explicitly
  labeled as less-grounded, rather than fabricating specifics.
- **Retry logic:** Shared LLM retry policy only.
- **Prompt template:** `prompts/library/interview/prepare.md`.
- **Metrics:** Traceability rate (% of talking points citing a specific
  resume/posting source) via golden-file tests.
- **Communication protocol:** Triggered by the orchestrator watching
  for `Application.status == "interview_scheduled"` transitions (via
  `application_events`), not polled by the agent itself.

---

## 11. Career Analytics Agent

- **Purpose:** Aggregate application history into actionable trends.
- **Responsibilities:** Compute response/interview/offer rates by role
  type, seniority, and source; surface simple, human-checkable
  statistics — not speculative predictions.
- **Inputs:** All `applications` + `application_events` +
  `job_postings` for the user.
- **Outputs:** `AnalyticsReport` (computed on read, `database.md` §18).
- **Tools:** Deterministic aggregation (no LLM call required for the
  core statistics — `rules.md` §Performance Guidelines); an optional
  LLM-generated narrative summary layer may use an LLM purely for
  prose, never for the numbers themselves.
- **Memory:** Reads `applications`, `application_events`,
  `job_postings`; writes nothing (pure computation).
- **Failure handling:** Insufficient history (e.g., <5 applications) →
  returns a report explicitly stating "not enough data" rather than
  misleading rates from a tiny sample.
- **Retry logic:** N/A for the deterministic path; shared LLM retry
  policy for the optional narrative layer.
- **Prompt template:** `prompts/library/career_analytics/summarize.md`
  (optional narrative layer only).
- **Metrics:** Numeric correctness verified against hand-computed
  fixture aggregates (`testing.md`); this agent's own output is not
  "graded" by an LLM judge since the numbers are deterministic.
- **Communication protocol:** Read-only consumer of the tracking system
  of record; feeds `jobhunt report` (HTML dashboard, `design.md` §1).

---

## Future Agents (see `roadmap.md` for full detail — designed later, not now)

LinkedIn Agent, Networking Agent, Salary Negotiation Agent, Visa
Requirement Agent, Research Position Agent, Scholarship Agent,
Professor Finder Agent, Publication Matching Agent all follow the exact
same template as above once scheduled into a phase — this section is
intentionally not pre-designed in detail to avoid speculative work
ahead of an actual phase assignment (`rules.md` AI Coding Rule 2).
