# Implementation Order — JOB_HUNT

Status: Draft v1.0 · Last updated: 2026-08-02

This is the **exact, dependency-respecting build sequence**, at the
granularity of `tasks.md` task IDs. Do not reorder to "get to the
interesting part" (e.g., building Resume Customization before the LLM
layer exists) — every step here is unlocked strictly by the steps
before it. If a step seems skippable, check `tasks.md`'s stated
Dependencies for that task before skipping it.

1. **T1.1** Repo & packaging scaffold — nothing else can start without
   an installable package.
2. **T1.2** Lint/type/format tooling — enforced from commit #1, not
   retrofitted later.
3. **T1.3** CI pipeline skeleton — so every subsequent step is checked
   as it lands.
4. **T1.4** Package tree skeleton — gives every later file a correct
   home.
5. **T1.5** Logging config skeleton — every agent from Phase 5 onward
   emits log events; the sink must exist first.
6. **T4.1** Core Pydantic schemas — the shared vocabulary. Built before
   config/LLM because nothing downstream can be typed without it, and
   it has zero internal dependencies itself.
7. **T2.1** Settings loader — needed by the LLM layer (next) and by
   every source/agent's config lookups.
8. **T2.2** `.env` secret handling — required before any real provider
   adapter is tested against even a recorded cassette (the loader path
   must exist).
9. **T2.3** Feature flags — needed before `AgentRegistry` has anything
   to enable/disable meaningfully.
10. **T3.1** `LLMProvider` protocol + schemas — the contract every
    adapter and every agent codes against.
11. **T3.5** Retry/backoff policy — built alongside the protocol so no
    adapter is ever written without it (never retrofitted per-adapter).
12. **T3.2** Anthropic adapter — first concrete provider (matches the
    maintainer's primary provider).
13. **T3.3** OpenAI adapter — second provider, proves the abstraction
    (`decisions.md` ADR-0003) actually holds for a second vendor.
14. **T3.4** Ollama adapter — third provider, local — lowest priority,
    can slip past Phase 3 if needed without blocking anything else.
15. **T4.2** SQLAlchemy models — now that schemas (step 6) exist to
    mirror.
16. **T4.3** Alembic setup + initial migration — immediately after
    models, never let code and migrations drift apart even for one
    commit.
17. **T4.4** Repositories — the only storage-access surface agents are
    allowed to use.
18. **T5.1** CV file parsers — first domain-specific logic; needs only
    the package skeleton (step 4).
19. **T5.2** Resume Analysis Agent + prompt — first real agent; needs
    LLM (step 12), schemas/storage (steps 6, 15–17), and parsers
    (step 18). **This is the first point at which the system produces
    a real artifact (`CandidateProfile`) — treat it as the first true
    milestone.**
20. **T5.3** Onboarding command (`/setup`) — first Claude Code command;
    proves the thin-wrapper pattern (`decisions.md` ADR-0004) end to
    end before any other command is built.
21. **T6.1** Skill Gap Agent + prompt — first agent built *after* the
    pattern from step 19 is proven; should reuse its structure directly.
22. **T7.1** Source connector interface — before any concrete connector.
23. **T7.2** First API-based connector — validates the interface
    against a real, non-trivial source.
24. **T7.3** Manual paste/import connector — validates the interface
    against a structurally different (no-API) source, proving the
    abstraction isn't overfit to one shape.
25. **T7.4** Job Search Agent + dedup — needs both connectors (steps
    23, 24) to test dedup logic meaningfully across sources.
26. **T8.1** Job Matching Agent + prompt — needs a real
    `CandidateProfile` (step 19) and real `JobPosting`s (step 25).
27. **T9.1** Ranking function + command — trivial once Matching (step
    26) exists; deliberately kept last among the "sourcing" cluster
    since it's pure post-processing.
28. **T10.1** ATS Optimization Agent + prompt — needs profile + posting
    (steps 19, 25); independent of Matching (step 26) but sequenced
    after it here because Resume Customization (next) needs both.
29. **T11.1** `DocumentRenderer` + Jinja2/LaTeX pipeline — the riskiest,
    highest-complexity piece (`phases.md` Phase 11 = L complexity);
    built as its own step before wiring an agent to it, so LaTeX/system
    dependency issues are isolated from agent-logic bugs.
30. **T11.2** PDF verification step — immediately after the renderer,
    since an unverified renderer is not acceptable to ship even
    internally (`decisions.md` ADR-0007).
31. **T11.3** Resume Customization Agent (drafter→reviewer loop) — the
    first agent combining a two-pass LLM interaction; needs ATS (step
    28) and the renderer (steps 29–30).
32. **T12.1** Cover letter template — reuses the renderer (step 29).
33. **T12.2** Cover Letter Agent + prompt — needs the tailored resume
    (step 31) for consistency checking.
34. **T13.1** Email Generation Agent + prompt — needs the cover letter
    (step 33).
35. **T14.1** Application/Event tables + repo — if not already fully
    covered by step 17, finalize here since real application data
    (steps 31–34's outputs) now exists to model against concretely.
36. **T14.2** Application Tracking Agent + status API — the system of
    record; needs step 35.
37. **T14.3** `/outcome` command — thin wrapper over step 36.
38. **T15.1** Interview Prep Agent + prompt — needs Matching (step 26),
    Resume Customization (step 31), and Tracking (step 36) since it's
    triggered by a tracked status change.
39. **T16.1** Career Analytics Agent — needs real tracked history (step
    36) to compute anything meaningful.
40. **T16.2** HTML dashboard generator — needs step 39's output shape
    finalized first.
41. **T17.1** End-to-end pipeline fixture test — only possible once
    every agent in the pipeline (steps 19–40) exists.
42. **T17.2** Coverage & security CI gates (final thresholds) — last,
    since it's meant to certify the *whole* accumulated codebase, not
    gate individual features mid-build.
43. **T1.6** License decision reconfirmed — a checkpoint, not a build
    step; do this explicitly before step 44, not as an afterthought
    during it.
44. **T18.1** Public README + quickstart — written against the actual
    final CLI/command surface (steps 20, 25, 27, 34, 37, 40), not
    speculatively before it's stable.
45. **T18.2** Contribution scaffolding — needs step 44's content to
    reference correctly (setup steps, contribution norms).
46. **T18.3** License file + first tagged release + push to
    `sougataresearch/JOB_HUNT` — the terminal step, and the only one in
    this entire list that touches a shared/public system. **Requires
    explicit maintainer go-ahead at the time it happens** — this
    document authorizes the *plan*, not the act of pushing itself.

## What "No Shortcuts" Means Here

- Do not build Resume Customization (step 29+) before the LLM layer
  (steps 10–14) exists "to see how it looks" — there is nothing to
  call.
- Do not build a second job source (step 24) before the first (step
  23) is fully working — the interface (step 22) needs at least one
  proven implementation before a second is a useful test of the
  abstraction, not just more surface area.
- Do not write the public README (step 44) early "to think through the
  UX" — write UX notes in `design.md`/`progress_log.md` instead; the
  README documents what actually exists.
- Do not skip straight to Phase 18 packaging/release concerns before
  Phase 17's coverage/security gates are green — a release built on an
  unverified pipeline is not a real release.

See `phases.md` for the milestone-level view of this same sequence and
`tasks.md` for each step's full task definition (Priority, Difficulty,
Expected files, Completion checklist).
