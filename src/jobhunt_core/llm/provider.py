"""Provider-agnostic LLM access layer (decisions.md ADR-0003, api.md §5).

Agents depend on the ``LLMProvider`` Protocol below, never on a vendor
SDK directly. A provider instance is obtained via
:func:`get_provider_class` and injected into an agent through
``RunContext`` (design.md §4 dependency injection) — never constructed
ad hoc inside an agent.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from jobhunt_core.errors import LLMProviderError
from jobhunt_core.llm.types import LLMResponse, StructuredLLMResponse

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@runtime_checkable
class LLMProvider(Protocol):
    """The contract every LLM adapter implements."""

    name: ClassVar[str]

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Return a free-text completion for ``prompt``."""
        ...

    def complete_structured(
        self,
        prompt: str,
        *,
        model: str,
        response_schema: type[SchemaT],
        temperature: float = 0.0,
    ) -> StructuredLLMResponse[SchemaT]:
        """Return a schema-validated structured completion for ``prompt``."""
        ...


_PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {}


def register_provider(name: str) -> Callable[[type[LLMProvider]], type[LLMProvider]]:
    """Class decorator registering an ``LLMProvider`` implementation by name.

    The concrete mechanism behind decisions.md ADR-0008 for the LLM
    layer (api.md §9 Plugin API). ``jobhunt_core.llm.providers``
    explicitly imports every adapter module (rather than a filesystem
    walk), so registration always happens before
    :func:`get_provider_class` is called from real code — see
    final_review.md §1.3 on why this is an explicit import list, not a
    dynamic discovery step.

    Args:
        name: The config-facing provider name (e.g. ``"anthropic"``),
            matching a key under ``llm.providers`` in
            ``config/llm.yaml``.

    Returns:
        A decorator that registers the class and returns it unchanged.
    """

    def decorator(cls: type[LLMProvider]) -> type[LLMProvider]:
        _PROVIDER_REGISTRY[name] = cls
        return cls

    return decorator


def available_providers() -> list[str]:
    """Return the sorted names of every currently registered provider."""
    return sorted(_PROVIDER_REGISTRY)


def get_provider_class(name: str) -> type[LLMProvider]:
    """Look up a registered provider class by name.

    Args:
        name: The provider name to look up, e.g. ``"anthropic"``.

    Returns:
        The registered provider class (not yet instantiated).

    Raises:
        LLMProviderError: No provider is registered under ``name`` —
            usually means ``jobhunt_core.llm.providers`` was never
            imported, or ``config/llm.yaml`` names a provider that
            doesn't exist.
    """
    try:
        return _PROVIDER_REGISTRY[name]
    except KeyError as exc:
        raise LLMProviderError(
            f"No LLM provider registered under name '{name}'.",
            remedy=(
                f"Available providers: {available_providers()}. Check "
                "config/llm.yaml, and that jobhunt_core.llm.providers "
                "has been imported."
            ),
        ) from exc
