# Architecture Decision Records — JOB_HUNT

Status: Living document · Last updated: 2026-08-02

Format: each ADR states Context, Decision, Alternatives Considered, and
Consequences. **Do not re-litigate a settled ADR without new evidence**
— per this repo's own `rules.md` (mirroring the convention already in
use for `sougata_solver/decisions.md`). If new evidence emerges, add a
new ADR that *supersedes* the old one; never silently edit history.

---

## ADR-0001: Primary language & runtime — Python 3.11+

**Context:** The system spans NLP-ish text processing (CV parsing),
scraping/API integration (job sourcing), LLM orchestration, and document
generation. Candidate options: Python, TypeScript/Node, or a polyglot
split.

**Decision:** Python 3.11+ for the entire core (`jobhunt_core`), CLI,
and orchestration layer.

**Alternatives considered:**
- *TypeScript/Node* — strong async I/O, single language if a web UI is
  ever built, but weaker ecosystem for PDF/CV parsing and LaTeX
  tooling, and no advantage for a v1 with no web UI.
- *Polyglot (Python core + TS frontend)* — reasonable for a *future*
  web dashboard, but premature for v1, which has no web UI (`design.md`
  §1). Adds a second toolchain, dependency manager, and CI job for no
  v1 benefit.

**Consequences:** Full access to `pdfplumber`/`pypdf`, BeautifulSoup,
Playwright, Pydantic, and the broader Python LLM tooling ecosystem.
If a web dashboard is built later (`roadmap.md`), it can be added as a
separate frontend consuming `jobhunt_core` through a thin API layer
without rewriting the core — this ADR does not preclude that.

---

## ADR-0002: Deployment & storage model — local-first, single-user, SQLite

**Context:** v1 could target local-first single-user use, a self-hosted
web app, or a multi-tenant SaaS from day one.

**Decision:** Local-first CLI/desktop tool. Structured data in SQLite;
generated documents on the local filesystem. No server process, no
hosted multi-tenancy in v1.

**Alternatives considered:**
- *Self-hosted web app (FastAPI + React)* — adds a browser UI and a
  local server process for no v1 requirement; the primary UX is
  conversational (Claude Code), not a dashboard.
- *Cloud-hosted multi-user SaaS* — requires auth, billing, multi-tenant
  data isolation, and hosting infra; wildly out of proportion to a
  personal-tool v1 and explicitly out of scope (`PRD.md` §9).

**Consequences:** Zero hosting cost, zero infra to maintain, data never
leaves the user's machine except to the LLM provider and job sources
(privacy-friendly by construction). Trade-off: no multi-device sync and
no collaboration features in v1 — acceptable per `PRD.md` §3 Target
Users. `schemas/` models still carry an unused `user_id`-shaped
extension point so multi-user is a migration, not a rewrite, later
(`architecture.md` §8).

---

## ADR-0003: LLM access — custom provider-agnostic abstraction, not a single vendor SDK, not a gateway library

**Context:** Every agent needs to call an LLM. Options: hard-code
Anthropic's SDK; hard-code OpenAI's SDK; delegate multi-provider routing
to an existing gateway (LiteLLM, OpenRouter); or build a small in-repo
`LLMProvider` interface with adapters.

**Decision:** Build a minimal in-repo `LLMProvider` Protocol
(`api.md` §LLM API) with adapters for Anthropic, OpenAI, and local
models (Ollama), selected via `config/llm.yaml`. No hard dependency on
a third-party gateway library.

**Alternatives considered:**
- *Claude-first, others as fallback* — simpler initially, but couples
  every agent's prompt design to one vendor's tool-use/caching
  conventions, contradicting the goal of being usable by open-source
  contributors on any provider they have a key for.
- *LiteLLM/OpenRouter gateway* — less code to maintain, but adds an
  external dependency whose abstraction choices (error types, retry
  semantics) we don't control, for a surface area (3 providers) small
  enough to own directly. Revisit if the provider list grows past what
  a thin custom layer comfortably covers.

**Consequences:** Every agent codes against `LLMProvider.complete(...)`
and `LLMProvider.complete_structured(...)` (Pydantic-typed output), never
against `anthropic.Anthropic()` or `openai.OpenAI()` directly
(`rules.md`). New providers are added by implementing the Protocol, not
by touching agent code (`architecture.md` §6).

---

## ADR-0004: Claude Code as the primary UX layer, over a decoupled, importable core

**Context:** The user wants a UX like MadsLorentzen/ai-job-search
(Claude Code slash commands driving everything), but also wants an
open-source, testable, CI-friendly codebase (per this project's own
`rules.md`/testing conventions already established for `sougata_solver`).
A pure "Claude Code project" (logic embedded only in command prompts)
would be hard to unit test and would not be an importable Python
package.

**Decision:** Three-layer split (`architecture.md` §1): a
Claude-Code-independent core library (`jobhunt_core`, pip-installable,
fully unit-testable with no Claude Code dependency) + a scriptable
`jobhunt` CLI + `.claude/commands/` and `.claude/skills/` as a thin
conversational UX wrapper over both.

**Alternatives considered:**
- *Logic lives in Claude Code command prompts/skills only* — matches
  the reference repo most literally, fastest to prototype, but makes
  core logic untestable by `pytest` and unusable without Claude Code —
  rejected because it conflicts with `PRD.md` §6 Testability and the
  open-source contributor goal (`PRD.md` §7).
- *Web app with Claude API calls, no Claude Code integration* — loses
  the exact UX the user asked to emulate.

**Consequences:** Every Claude Code command is intentionally "thin" —
a few lines that call into `jobhunt_core`/`jobhunt` CLI and let the
conversation handle clarification. All actual logic is testable in
isolation. Slight duplication risk (command prompt drifting from CLI
behavior) is mitigated by commands *shelling out to or importing* the
same CLI entry points rather than reimplementing logic in prompt text
(`rules.md`).

---

## ADR-0005: Orchestration model — sequential staged pipeline (v1), not a graph engine

**Context:** The user's specified pipeline (Resume Analysis → Skill Gap
→ Job Search → Job Matching → ATS → Resume Customization → Cover Letter
→ Email → Tracking → Interview Prep → Analytics) is fundamentally
linear per-application, though individual stages can be re-run
independently.

**Decision:** v1 orchestration is a simple ordered-stage pipeline
(`orchestration/pipeline.py`) with persisted intermediate outputs, not a
general graph/DAG execution engine.

**Alternatives considered:**
- *Graph-based orchestrator (e.g., LangGraph-style state machine) from
  day one* — more powerful (conditional branching, parallel fan-out)
  but unnecessary complexity for a linear v1 pipeline, and a bigger
  dependency/learning surface for contributors.

**Consequences:** Simpler to implement, test, and reason about for v1.
Because the `Agent` protocol and registry are orchestrator-agnostic
(`architecture.md` §3), swapping in a graph engine later — e.g., for
parallel scoring across hundreds of postings, or conditional re-runs —
only touches `orchestration/`, never `agents/`. This is the explicit
upgrade path recorded in `architecture.md` §8.

---

## ADR-0006: Artifact storage — filesystem for binaries, SQLite rows for metadata only

**Context:** Generated PDFs, LaTeX sources, and raw scraped job-posting
HTML/JSON need to be stored somewhere durable and queryable.

**Decision:** Binary/large content lives on the filesystem under
`data/documents/` and `data/raw/`; SQLite rows store only metadata and a
relative file path reference.

**Alternatives considered:**
- *Store PDFs/HTML as DB blobs* — keeps everything in one file, but
  bloats the SQLite file, complicates backup/diffing, and makes
  documents harder to open directly in an editor/viewer during
  development.

**Consequences:** `data/documents/<application_id>/` is a self-contained,
inspectable, deletable unit per application. DB stays small and fast.
Requires a foreign-key-adjacent convention (path is relative to a known
root, validated on read) documented in `database.md`.

---

## ADR-0007: Document rendering — LaTeX for CV/cover letters, Jinja2 templating, drafter→reviewer verification loop

**Context:** Generated CVs and cover letters need to look professional
and be reliably ATS-parseable. Options: LaTeX (proven in the reference
repo), Markdown→PDF (via Pandoc/WeasyPrint), or HTML→PDF.

**Decision:** LaTeX (lualatex/xelatex) as the v1 rendering path for CVs
and cover letters, templated via Jinja2 (so LaTeX special characters and
dynamic content are handled safely — never raw Python string
interpolation into `.tex`), with a mandatory post-render verification
step: compile → extract text (`pdftotext`) → confirm the ATS-relevant
content round-trips as plain text before the document is presented to
the user. Generation follows a drafter→reviewer loop (a second,
fresh-context pass critiques the draft against the posting and formatting
rules) before the verification step, mirroring the pattern validated in
MadsLorentzen/ai-job-search.

**Alternatives considered:**
- *Markdown → Pandoc/WeasyPrint* — simpler toolchain, no LaTeX
  distribution dependency, but noticeably less control over
  professional typesetting (moderncv-style layouts) and less proven for
  this exact use case.
- *HTML → headless-browser PDF* — flexible styling via CSS, but heavier
  runtime dependency (a browser engine) for arguably worse typographic
  output than LaTeX for a CV specifically.

**Consequences:** Requires a LaTeX distribution as a system dependency
(`config.md`/`README.md` setup docs must call this out clearly). The
renderer is implemented behind a `DocumentRenderer` strategy interface
(`architecture.md` §4 Component Hierarchy) specifically so a
Markdown/HTML renderer can be added later as an alternative template
type without changing agent code (`decisions.md` ADR-0008 covers the
general template-registration mechanism).

---

## ADR-0008: Plugin/extension mechanism — decorator-based registries

**Context:** The system must support unlimited future agents, job
sources, document templates, and LLM providers without modifying
existing code (`PRD.md` §6, `architecture.md` §6).

**Decision:** A uniform pattern across all four extension points: a
module-level decorator (`@register_agent`, `@register_source`,
`@register_provider`) that adds the implementation to a registry
dict at import time, plus a corresponding YAML entry
(`config/agents.yaml`, `config/sources.yaml`, `config/llm.yaml`) to
enable/configure it. Document templates use a lighter-weight
`templates/registry.yaml` (no code registration needed, since templates
are data, not behavior).

**Alternatives considered:**
- *Entry-point-based plugin discovery (Python packaging entry_points)*
  — better for genuinely separate, independently-installed plugin
  *packages*, but heavier machinery than needed while all agents live
  in-tree; revisit if/when true third-party plugin packages (not just
  in-tree modules) become common (`roadmap.md` §Plugin Ecosystem).

**Consequences:** Adding a new agent is additive-only (new files +
one registry entry), directly enabling the extensibility success metric
in `PRD.md` §7 ("new agent added in ≤ 1 day"). If external plugin
*packages* become a real need post-OSS-release, this can be layered on
top of the same registry (entry points populate the same dict) without
breaking in-tree agents.

---

## ADR-0009: License — MIT (proposed)

**Context:** The project will be pushed to a public GitHub repository
(`sougataresearch/JOB_HUNT`) with the stated goal of eventually becoming
open source and accepting contributions (job-board integrations, CV
templates).

**Decision (proposed, pending final confirmation before first public
push):** MIT license — maximally permissive, minimal friction for
contributors and downstream users adapting it to their own CV/region.

**Alternatives considered:**
- *Apache 2.0* — adds explicit patent grant language; reasonable
  alternative if patent concerns ever become relevant, but adds
  complexity not currently needed for a career-tools project.
- *AGPL* — would force network-use copyleft, which is irrelevant for a
  local-first tool with no hosted service, and would likely deter the
  casual contributions this project wants (CV templates, job-source
  connectors).

**Consequences:** No `LICENSE` file has been added yet — this ADR
records the recommendation; final selection should be explicitly
confirmed by the maintainer before the repository is made public
(`README.md` §License).

---

## Superseded / Rejected Records

None yet. When an ADR above is later reversed, add a new numbered ADR
here describing what changed and why, and mark the original
"Superseded by ADR-00XX" in its heading — never delete a past decision.
