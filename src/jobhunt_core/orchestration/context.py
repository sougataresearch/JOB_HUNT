"""Builds a RunContext from Settings (architecture.md §6).

The factory that was deliberately deferred in Phase 3's progress_log
entry ("that wiring naturally belongs where RunContext is built...
Phase 5+") -- Phase 5 is where the first agent needs it.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from jobhunt_core import sources as _sources  # noqa: F401 -- registers connectors
from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.config.settings import Settings
from jobhunt_core.errors import LLMProviderError, SourceFetchError
from jobhunt_core.llm import providers as _providers  # noqa: F401 -- registers adapters
from jobhunt_core.llm.provider import LLMProvider, get_provider_class
from jobhunt_core.sources.base import JobSource, get_source_class
from jobhunt_core.storage.repositories import (
    ApplicationRepo,
    ATSRepo,
    DocumentRepo,
    InterviewRepo,
    JobRepo,
    MatchRepo,
    ProfileRepo,
)


def build_llm_provider(provider_name: str, settings: Settings) -> LLMProvider:
    """Construct a configured ``LLMProvider`` instance for ``provider_name``.

    A small, explicit if/elif dispatch rather than a generic
    ``from_settings()`` classmethod convention across providers --
    with only 3 known providers and differing constructor needs (API
    key vs. host), this stays simpler than that abstraction would be
    (rules.md no-speculative-abstraction). Revisit if a 4th provider
    makes the dispatch unwieldy.

    Args:
        provider_name: e.g. ``"anthropic"``.
        settings: The loaded application settings.

    Returns:
        A constructed, ready-to-use ``LLMProvider``.

    Raises:
        LLMProviderError: No config exists for ``provider_name``, its
            required API key is not set, or the name is unrecognized.
    """
    provider_cls = get_provider_class(provider_name)
    provider_cfg = settings.llm.providers.get(provider_name)
    if provider_cfg is None:
        raise LLMProviderError(
            f"No provider config found for '{provider_name}' in llm.yaml.",
            remedy="Add an entry under llm.providers in config/llm.yaml.",
        )

    if provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMProviderError(
                "ANTHROPIC_API_KEY is not set.", remedy="Add it to your .env file."
            )
        return provider_cls(  # type: ignore[call-arg]
            api_key=settings.anthropic_api_key,
            timeout_s=provider_cfg.timeout_s,
            max_retries=provider_cfg.max_retries,
            cost_per_mtok_in=provider_cfg.cost_per_mtok_in,
            cost_per_mtok_out=provider_cfg.cost_per_mtok_out,
        )
    if provider_name == "openai":
        if not settings.openai_api_key:
            raise LLMProviderError("OPENAI_API_KEY is not set.", remedy="Add it to your .env file.")
        return provider_cls(  # type: ignore[call-arg]
            api_key=settings.openai_api_key,
            timeout_s=provider_cfg.timeout_s,
            max_retries=provider_cfg.max_retries,
            cost_per_mtok_in=provider_cfg.cost_per_mtok_in,
            cost_per_mtok_out=provider_cfg.cost_per_mtok_out,
        )
    if provider_name == "ollama":
        return provider_cls(  # type: ignore[call-arg]
            host=settings.ollama_host,
            timeout_s=provider_cfg.timeout_s,
            max_retries=provider_cfg.max_retries,
            cost_per_mtok_in=provider_cfg.cost_per_mtok_in,
            cost_per_mtok_out=provider_cfg.cost_per_mtok_out,
        )
    raise LLMProviderError(f"Unknown provider '{provider_name}'.")


def build_sources(settings: Settings) -> dict[str, JobSource]:
    """Construct every enabled ``JobSource`` from ``settings.sources`` (api.md §2).

    A small, explicit if/elif dispatch, same reasoning as
    :func:`build_llm_provider`: with only 2 known sources and
    differing constructor needs (board tokens vs. nothing), this stays
    simpler than a generic ``from_settings()`` convention would
    (rules.md no-speculative-abstraction).

    Args:
        settings: The loaded application settings.

    Returns:
        Every enabled source, keyed by name. Disabled sources are
        omitted entirely (config.md §Config Validation Rules).
    """
    resolved: dict[str, JobSource] = {}
    for name, cfg in settings.sources.items():
        if not cfg.enabled:
            continue
        source_cls = get_source_class(name)
        if name == "greenhouse":
            resolved[name] = source_cls(boards=cfg.boards)  # type: ignore[call-arg]
        elif name == "manual_import":
            resolved[name] = source_cls()
        else:
            raise SourceFetchError(
                f"No construction rule for source '{name}' in build_sources().",
                remedy="Add an elif branch for it in orchestration/context.py.",
            )
    return resolved


def build_repository_bundle(session: Session) -> RepositoryBundle:
    """Construct a ``RepositoryBundle``, all repositories sharing one session."""
    return RepositoryBundle(
        profiles=ProfileRepo(session),
        jobs=JobRepo(session),
        matches=MatchRepo(session),
        ats=ATSRepo(session),
        applications=ApplicationRepo(session),
        interviews=InterviewRepo(session),
        documents=DocumentRepo(session),
    )


def build_run_context(settings: Settings, session: Session, *, agent_name: str) -> RunContext:
    """Construct a ``RunContext`` for running ``agent_name``.

    Args:
        settings: The loaded application settings.
        session: An open SQLAlchemy session.
        agent_name: The agent this context will be used to run, e.g.
            ``"resume_analysis"`` -- used to resolve which provider to
            build (the agent's own config, falling back to
            ``llm.default_provider``).

    Returns:
        A ready-to-use ``RunContext``.
    """
    agent_cfg = settings.agents.get(agent_name)
    provider_name = (agent_cfg.provider if agent_cfg else None) or settings.llm.default_provider
    llm = build_llm_provider(provider_name, settings)
    repos = build_repository_bundle(session)
    sources = build_sources(settings)
    return RunContext(settings=settings, llm=llm, repos=repos, sources=sources)
