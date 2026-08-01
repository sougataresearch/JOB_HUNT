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
