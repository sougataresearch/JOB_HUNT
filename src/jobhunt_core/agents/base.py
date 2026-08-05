"""The common Agent protocol, RunContext, and AgentResult (api.md §0).

Every agent implements ``Agent`` below and receives only its typed
input plus a ``RunContext`` -- never a global singleton, never a
directly-constructed ``LLMProvider``/repository (design.md §4
dependency injection), which is what keeps agents unit-testable with
fakes (testing.md).
"""

from __future__ import annotations

import uuid
from typing import ClassVar, Generic, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from jobhunt_core.config.settings import Settings
from jobhunt_core.llm.provider import LLMProvider
from jobhunt_core.storage.repositories import (
    ApplicationRepo,
    ATSRepo,
    InterviewRepo,
    JobRepo,
    MatchRepo,
    ProfileRepo,
)

InT = TypeVar("InT", bound=BaseModel, contravariant=True)
OutT = TypeVar("OutT", bound=BaseModel, covariant=True)


class RepositoryBundle(BaseModel):
    """One repository per aggregate, bundled for ``RunContext`` (api.md §7)."""

    profiles: ProfileRepo
    jobs: JobRepo
    matches: MatchRepo
    ats: ATSRepo
    applications: ApplicationRepo
    interviews: InterviewRepo

    model_config = ConfigDict(arbitrary_types_allowed=True)


class RunContext(BaseModel):
    """Everything an agent needs besides its typed input (api.md §0).

    Construct via ``orchestration.context.build_run_context()``, not
    directly, outside of tests.
    """

    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    settings: Settings
    llm: LLMProvider
    repos: RepositoryBundle

    model_config = ConfigDict(arbitrary_types_allowed=True)


class AgentResult(BaseModel, Generic[OutT]):
    """Wraps a typed agent output with run metadata (api.md §0, design.md §9).

    The orchestrator (not the agent itself) turns this into a
    structured ``RunEvent`` log line (design.md §9, api.md §8) once
    ``schemas``/logging for that exists -- deferred until an
    orchestrator that runs multiple agents in sequence is built
    (Phase 6+; the CLI calls agents directly for now).
    """

    output: OutT
    prompt_version: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_estimate_usd: float = 0.0
    latency_ms: int = 0
    warnings: list[str] = Field(default_factory=list)


class Agent(Protocol[InT, OutT]):
    """The contract every agent implements."""

    name: ClassVar[str]
    input_schema: ClassVar[type[BaseModel]]
    output_schema: ClassVar[type[BaseModel]]

    def run(self, input: InT, ctx: RunContext) -> AgentResult[OutT]:
        """Run the agent on ``input`` using ``ctx``, returning a wrapped result."""
        ...
