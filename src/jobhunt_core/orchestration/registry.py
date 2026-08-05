"""Agent registry (architecture.md §6, decisions.md ADR-0008).

Concrete mechanism behind final_review.md §1.3's mitigation: registered
agents are discovered via ``jobhunt_core.agents`` explicitly importing
every agent module (not a filesystem walk), so ``get_agent_class`` is
guaranteed to see every agent once that package has been imported --
see ``agents/__init__.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from jobhunt_core.agents.base import Agent
from jobhunt_core.errors import JobHuntError

# Agent[Any, Any] (not Agent[BaseModel, BaseModel]): each concrete agent's
# run() narrows InT to its own specific input schema, which is unsound to
# assign to a fixed Agent[BaseModel, BaseModel] under InT's contravariance
# (mypy correctly rejects it -- confirmed by running mypy, not assumed).
# A heterogeneous registry of differently-typed Protocol implementations is
# exactly where Any is the standard, deliberate escape hatch, not laziness.
_AGENT_REGISTRY: dict[str, type[Agent[Any, Any]]] = {}


def register_agent(
    name: str,
) -> Callable[[type[Agent[Any, Any]]], type[Agent[Any, Any]]]:
    """Class decorator registering an ``Agent`` implementation by name.

    Args:
        name: The config-facing agent name (e.g. ``"resume_analysis"``),
            matching a key under ``agents`` in ``config/agents.yaml``.

    Returns:
        A decorator that registers the class and returns it unchanged.
    """

    def decorator(cls: type[Agent[Any, Any]]) -> type[Agent[Any, Any]]:
        _AGENT_REGISTRY[name] = cls
        return cls

    return decorator


def available_agents() -> list[str]:
    """Return the sorted names of every currently registered agent."""
    return sorted(_AGENT_REGISTRY)


def get_agent_class(name: str) -> type[Agent[Any, Any]]:
    """Look up a registered agent class by name.

    Args:
        name: The agent name to look up, e.g. ``"resume_analysis"``.

    Returns:
        The registered agent class (not yet instantiated).

    Raises:
        JobHuntError: No agent is registered under ``name`` -- usually
            means ``jobhunt_core.agents`` was never imported, or
            ``config/agents.yaml`` names an agent that doesn't exist.
    """
    try:
        return _AGENT_REGISTRY[name]
    except KeyError as exc:
        raise JobHuntError(
            f"No agent registered under name '{name}'.",
            remedy=(
                f"Available agents: {available_agents()}. Check "
                "config/agents.yaml, and that jobhunt_core.agents has "
                "been imported."
            ),
        ) from exc
