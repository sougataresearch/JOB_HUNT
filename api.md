# Internal API Design — JOB_HUNT

Status: Draft v1.0 · Last updated: 2026-08-02

These are **internal Python interface contracts** — not a network API
(v1 has no server, per `decisions.md` ADR-0002). Every contract here is
a `Protocol`/ABC + Pydantic schema pair. Concrete implementations live
under `src/jobhunt_core/` per `folder_structure.md`. All error types
referenced below extend `JobHuntError` (`design.md` §10).

## 0. Common: the Agent API

Every agent in the system, regardless of domain, implements this:

```python
class RunContext(BaseModel):
    run_id: str
    settings: Settings
    llm: LLMProvider
    repos: RepositoryBundle          # one attribute per repository
    model_config = ConfigDict(arbitrary_types_allowed=True)

class AgentResult(BaseModel, Generic[OutT]):
    output: OutT
    prompt_version: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_estimate_usd: float
    latency_ms: int
    warnings: list[str] = []

class Agent(Protocol[InT, OutT]):
    name: ClassVar[str]
    input_schema: ClassVar[type[InT]]
    output_schema: ClassVar[type[OutT]]

    def run(self, input: InT, ctx: RunContext) -> AgentResult[OutT]: ...
```

Registration:

```python
def register_agent(name: str) -> Callable[[type[Agent]], type[Agent]]: ...
```

Errors: agents raise `AgentInputError` (bad input, not retried),
`LLMProviderError` (bubbled from the LLM layer, retry already
attempted there), or `RenderError` (document agents only).

## 1. CV Parser API

```python
class ParsedDocument(BaseModel):
    raw_text: str
    sections: dict[str, str]         # best-effort section splitting
    source_format: Literal["pdf", "docx", "markdown"]

class CVParser(Protocol):
    def supports(self, file_path: Path) -> bool: ...
    def parse(self, file_path: Path) -> ParsedDocument: ...
```

- Implementations: `PDFParser`, `DOCXParser`, `MarkdownParser`
  (`documents/parsers/`).
- Resolution: `ParserRegistry.for_file(path)` returns the first parser
  whose `supports()` is true; raises `UnsupportedFormatError` if none
  match.
- Consumed by: Resume Analysis Agent only (`agents.md`).

## 2. Job Search API

```python
class JobSource(Protocol):
    name: ClassVar[str]

    def search(self, query: SearchQuery, ctx: RunContext) -> list[RawPosting]: ...

class SearchQuery(BaseModel):
    keywords: list[str]
    locations: list[str] = []
    remote_ok: bool = True
    posted_within_days: int | None = None

class RawPosting(BaseModel):
    source: str
    source_id: str
    title: str
    company: str
    location: str
    url: str
    raw_content: str                 # untrusted — see design.md §12
    fetched_at: datetime
```

- Registration: `@register_source("greenhouse")` etc.
- `Job Search Agent` calls every enabled source, normalizes
  `RawPosting → JobPosting` (`schemas/job.py`), and dedupes
  (`agents.md` §Job Search Agent).
- Failure isolation: a `SourceFetchError` from one source is caught by
  the orchestrator per-source, not per-batch (`design.md` §10).

## 3. Ranking API

```python
class Ranker(Protocol):
    def rank(self, scores: list[MatchScore]) -> list[RankedPosting]: ...

class RankedPosting(BaseModel):
    job_id: str
    score: MatchScore
    rank: int
```

- v1 implementation is a pure function (sort by `MatchScore.value`
  descending, stable tie-break by `posted_at` descending) — no LLM call
  needed for ranking itself, only for the underlying score
  (`rules.md` §Performance Guidelines: don't use an LLM where a
  deterministic function suffices).

## 4. Prompt API

```python
class PromptTemplate(BaseModel):
    name: str
    version: str
    body: str                        # Jinja2 template text
    output_schema: type[BaseModel] | None

class PromptLoader(Protocol):
    def load(self, agent_domain: str, name: str, version: str | None = None) -> PromptTemplate: ...
    def render(self, template: PromptTemplate, **vars: Any) -> str: ...
```

- `version=None` resolves to the latest version for that
  `(agent_domain, name)` pair (`prompts.md` §Versioning).
- `render()` is the only place untrusted content (posting text) is
  interpolated — always through an explicit `{{ untrusted_content }}`
  block wrapped in delimiter tags the prompt's instructions reference
  (`design.md` §12, `prompts.md` §Guardrails).

## 5. LLM API

```python
class LLMProvider(Protocol):
    name: ClassVar[str]

    def complete(self, prompt: str, *, model: str, temperature: float = 0.0,
                 max_tokens: int | None = None) -> LLMResponse: ...

    def complete_structured(self, prompt: str, *, model: str,
                             response_schema: type[T],
                             temperature: float = 0.0) -> StructuredLLMResponse[T]: ...

class LLMResponse(BaseModel):
    text: str
    tokens_in: int
    tokens_out: int
    cost_estimate_usd: float
    latency_ms: int

class StructuredLLMResponse(LLMResponse, Generic[T]):
    parsed: T
```

- Registration: `@register_provider("anthropic")`,
  `@register_provider("openai")`, `@register_provider("ollama")`.
- Selection: `config/llm.yaml` maps each agent (or a default) to a
  `provider + model` pair — agents never hardcode a model name
  (`config.md`).
- Retries: implemented once in `llm/retry.py`, wrapping every provider
  adapter uniformly (`design.md` §11); raises `LLMProviderError` after
  exhausting retries.

## 6. Email API

```python
class EmailDraft(BaseModel):
    to: str | None                    # None if unknown — never guessed
    subject: str
    body: str
    attachments: list[Path]
    status: Literal["draft"] = "draft"

class EmailDrafter(Protocol):
    def draft(self, posting: JobPosting, cover_letter: RenderedDocument,
              resume: RenderedDocument, ctx: RunContext) -> EmailDraft: ...
```

- There is deliberately **no `send()` method in v1** — sending is a
  human action outside this API surface (`PRD.md` §9). A future `Email
  Agent` send-capability (if ever added) would be a new, explicitly
  reviewed API addition, not a silent extension of `EmailDrafter`.

## 7. Storage API

```python
class Repository(Protocol[T]):
    def get(self, id: str) -> T | None: ...
    def list(self, **filters: Any) -> list[T]: ...
    def save(self, entity: T) -> T: ...
    def delete(self, id: str) -> None: ...

class RepositoryBundle(BaseModel):
    profiles: ProfileRepo
    jobs: JobRepo
    matches: MatchRepo
    applications: ApplicationRepo
    interviews: InterviewRepo
    model_config = ConfigDict(arbitrary_types_allowed=True)
```

- Every repository wraps a single SQLAlchemy model (`database.md`); no
  agent imports SQLAlchemy directly — only repositories do
  (`architecture.md` §2 dependency rule).
- `ApplicationRepo` additionally exposes
  `add_event(application_id: str, event: ApplicationEvent) -> None`
  since status history is append-only (`design.md` §3).

## 8. Logging API

```python
class RunEvent(BaseModel):
    run_id: str
    agent: str
    prompt_version: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_estimate_usd: float
    latency_ms: int
    status: Literal["ok", "warning", "error"]
    warnings: list[str] = []

def log_run_event(event: RunEvent) -> None: ...
def configure_logging(settings: Settings) -> None: ...
```

- `log_run_event` is called once per agent invocation by the
  orchestrator (not by the agent itself) so logging can never be
  accidentally skipped by a new agent forgetting to call it
  (`design.md` §9).

## 9. Plugin API

```python
def register_agent(name: str) -> Callable[[type], type]: ...
def register_source(name: str) -> Callable[[type], type]: ...
def register_provider(name: str) -> Callable[[type], type]: ...

class AgentRegistry:
    def available(self) -> list[str]: ...
    def get(self, name: str) -> type[Agent]: ...
```

- This is the concrete mechanism behind `decisions.md` ADR-0008 and
  `architecture.md` §6 — every future agent/source/provider/template
  goes through these functions, never through editing
  `orchestration/pipeline.py` directly.

## 10. Future APIs (not built in v1, contracts reserved)

- **LinkedIn API** — `LinkedInAgent` producing `ProfileOptimization`
  suggestions; will reuse the `Agent`/`LLMProvider` contracts unchanged.
- **Gmail Sync API** — a `StatusSignalDetector` protocol translating
  inbox events into `ApplicationEvent`s; will consume `Storage API`
  §7 unchanged.
- **Notion/HTML Export API** — an `ExporterProtocol` parallel to
  `documents/report_renderer.py`, for publishing tracking data
  elsewhere; read-only consumer of `Storage API`.
- **Networking / Salary Negotiation / Visa / Research Position /
  Scholarship agents** (`roadmap.md`) — all expected to fit the
  existing `Agent` Protocol with new domain-specific schemas; no new
  top-level API section anticipated unless one needs a genuinely new
  capability (e.g., a `send()`-capable API would need its own ADR, per
  §6 above).
