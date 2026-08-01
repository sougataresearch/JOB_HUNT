# Final Review — Self-Critique of the JOB_HUNT Architecture

Status: Draft v1.0 · Last updated: 2026-08-02

Per the original brief's requirement to review the whole architecture
critically rather than just present it, this document lists genuine
weaknesses, scalability risks, and complexity that should be watched or
reconsidered — written the same way an outside principal engineer would
red-team this design before a team commits months to it.

## 1. Weaknesses

### 1.1 SQLite concurrency is a real, if currently low-probability, risk
SQLite's writer-locking model is fine for a single CLI process, but the
moment two things write concurrently — e.g., a background `/scrape`
running while an `/apply` is also writing, or a future Gmail-sync
background job — "database is locked" errors become likely. **This
architecture does not currently specify WAL mode or a busy-timeout
policy.** Mitigation: enable `PRAGMA journal_mode=WAL` and a sane
busy-timeout in `storage/db.py` from Phase 4 onward, and add a
regression test that runs two concurrent writers deliberately. This
should be folded into `tasks.md` T4.2 rather than discovered later.

### 1.2 LaTeX as a hard system dependency is a real adoption barrier
`decisions.md` ADR-0007 chose LaTeX for quality reasons, but a LaTeX
distribution (several hundred MB, non-trivial install on Windows
specifically — relevant since the maintainer's own machine is Windows)
is a meaningfully higher setup barrier than a pure-Python rendering
path, working directly against the open-source-readiness goal in
`PRD.md` §7. **This is a real, acknowledged trade-off, not an oversight
— but the docs currently undersell the cost.** Improvement: Phase 18's
README/quickstart must include first-class, OS-specific LaTeX install
instructions (including a Windows path via MiKTeX/TeX Live), and
`roadmap.md` should more concretely commit to a Markdown/WeasyPrint
fallback renderer as a near-term (not just hypothetical) alternative
for contributors who don't want to install LaTeX at all — right now
it's mentioned as "could be added later" with no urgency attached.

### 1.3 Plugin registries rely on import-time side effects — a classic footgun
`@register_agent`/`@register_source`/`@register_provider`
(`decisions.md` ADR-0008) only populate the registry if the decorated
module has actually been imported somewhere. Nothing in `architecture.md`
or `api.md` currently specifies *what guarantees every agent module gets
imported* before the registry is queried. Without an explicit
`discover_plugins()` step (walking `agents/`, `sources/`,
`llm/providers/` and importing everything), a new agent file can be
added, fully correct, and silently never appear in the registry — a
frustrating, hard-to-debug failure mode for exactly the open-source
contributors this project wants to attract. **Improvement:** add an
explicit, tested `orchestration/discover_plugins()` function called
once at CLI/command startup, and a test asserting
`len(AgentRegistry.available()) == <expected count>` so a
silently-unregistered agent fails CI, not a user's first run.

### 1.4 Config is single-user shaped even though schemas anticipate multi-user
`database.md` gives every table an unused `user_id` column
(`decisions.md` ADR-0002's stated migration path), but `config/agents.yaml`
and friends are entirely global, singleton, file-based config with no
analogous per-user hook. If multi-user ever actually happens
(`roadmap.md` §Enterprise), the data layer migrates gracefully but the
config layer does not — this is an inconsistency between two decisions
that were made independently. Not worth solving now (`rules.md`
no-speculative-abstraction), but `decisions.md` ADR-0002 should note
this gap explicitly so it isn't rediscovered as a surprise later.

## 2. Scalability Problems

### 2.1 "Computed on read" analytics will eventually need reconsidering
`database.md` §18 deliberately avoids a persisted analytics table to
prevent a second source of truth. This is correct at hundreds of
applications, but if a user runs this for years, "recompute from full
event history on every `jobhunt report`" scales linearly with lifetime
application count — likely fine (even 10,000 events is nothing for
SQLite), but worth an explicit note rather than an implicit assumption:
**this should be revisited only if `jobhunt report` latency is ever
user-visibly slow, not preemptively optimized.**

### 2.2 Sequential pipeline orchestration doesn't parallelize batch scoring
`decisions.md` ADR-0005 chose a simple sequential pipeline for v1.
That's the right call for *per-application* flow, but Job Matching
Agent scoring a batch of 200 postings (`tasks.md` T3.1 rate-limit note
references exactly this number) currently has no stated concurrency
model — if each score is a separate sequential LLM call, 200 postings
at even 2 seconds each is over 6 minutes of wall-clock time for one
`/rank` pass. **This is a real latency problem the current design
doesn't address.** Improvement: the LLM API (`api.md` §5) should
explicitly support a batch/concurrent-call mode for read-only scoring
operations (bounded by a concurrency limit in `config.md` §Rate
Limits), decided as an explicit ADR when Phase 8 is actually
implemented — flagging it now so it isn't a surprise mid-phase.

### 2.3 Prompt version proliferation has no retention policy
`rules.md` mandates a new prompt version rather than an in-place edit
every time a used prompt changes. Over a multi-year project this is
correct for reproducibility but will accumulate many versions with no
stated pruning/archival policy. Low risk at current scale (a few dozen
prompts × a handful of versions each is nothing), but `prompts.md`
should eventually state a policy (e.g., "versions referenced by at
least one `agent_run` row are never deleted; unreferenced draft
versions may be pruned") rather than leaving it unstated indefinitely.

## 3. Unnecessary Complexity

### 3.1 Three LLM provider adapters in the near-term plan may be premature
`decisions.md` ADR-0003 and `phases.md` Phase 3 schedule Anthropic
(P0), OpenAI (P1), and Ollama (P2) adapters essentially back-to-back.
Given this is explicitly a personal-tool-first project (`PRD.md` §3),
building and *testing* three full provider adapters before a single
real agent exists is arguably over-investment relative to actual
near-term need. **This isn't wrong** (the interface should exist from
day one to avoid lock-in), but the *task priority already reflects
this correctly* (OpenAI P1, Ollama P2, both markable as "stub +
defer" if time-boxed) — flagging here only so a future implementer
doesn't feel obligated to fully build all three before moving on to
Phase 4.

### 3.2 Drafter→reviewer loop on every document-generating agent may be
### more machinery than every agent needs
`decisions.md` ADR-0007 applies the drafter→reviewer pattern to Resume
Customization and (by extension, via the shared renderer) Cover
Letter. For agents that are pure single-pass judgment calls with a
clear, checkable schema (e.g., ATS Optimization, ranking) a second
review pass genuinely adds needed quality control since the output is
free-text-heavy and fabrication-prone. But if this pattern gets
reflexively copy-pasted onto every future agent (e.g., a future
Skill Gap Agent doesn't obviously need a reviewer pass — its output is
lower-stakes and more structured), that's needless latency/cost.
**Recommendation:** treat drafter→reviewer as a documented *option* in
the `Agent` base pattern, applied only where `agents.md` explicitly
calls for it (currently: Resume Customization, Cover Letter) — not a
default every new agent must justify skipping.

## 4. Suggested Improvements (rolled up)

1. Add WAL mode + busy-timeout to `storage/db.py` from Phase 4 (§1.1).
2. Commit to a concrete Markdown/WeasyPrint fallback renderer milestone
   in `roadmap.md`, not just a hypothetical mention (§1.2).
3. Add an explicit, tested `discover_plugins()` step and a registry-count
   test to `orchestration/` (§1.3).
4. Add a one-line acknowledgment in `decisions.md` ADR-0002 that config
   is not yet multi-user-shaped, so the gap is a known trade-off, not a
   surprise (§1.4).
5. Add a concurrency/batch mode to the LLM API for read-only scoring
   before Phase 8 ships, with its own ADR (§2.2).
6. State a prompt-version retention policy in `prompts.md` once the
   library grows past a handful of versions per prompt — not urgent now
   (§2.3).
7. Keep drafter→reviewer scoped to the agents that currently call for
   it in `agents.md`; don't let it become a reflexive default for every
   future agent (§3.2).

## 5. What's Solid (worth explicitly confirming, not just critiquing)

- The layered dependency structure (`schemas`/`config` at the center,
  nothing importing back into `agents`) is a genuinely good fit for
  this problem and should hold up well as more agents are added.
- The plugin/registry mechanism (once §1.3's discovery gap is closed)
  correctly achieves the "add an agent without touching existing code"
  goal that was the single most-repeated requirement in the original
  brief.
- The no-fabrication rule being enforced at three independent layers
  (prompt guardrail text, reviewer pass, PDF verification step) rather
  than relying on any single one is a sound defense-in-depth choice
  given how much this project's actual value depends on it.
- Keeping the documentation suite at repo root, matching this
  workspace's existing convention, is a good call for AI-agent-driven
  development specifically — it's exactly the kind of consistency that
  makes future Claude Code sessions productive without rediscovery.
