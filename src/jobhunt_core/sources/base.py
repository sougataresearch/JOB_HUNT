"""Job source connector interface (tasks.md T7.1, api.md §2).

Agents depend on the ``JobSource`` Protocol below, never on a
connector's concrete HTTP/file-reading details directly. A source
instance is obtained via :func:`get_source_class` and injected into an
agent through ``RunContext`` (design.md §4 dependency injection) — the
same registry shape as ``llm/provider.py``'s ``LLMProvider`` registry
(decisions.md ADR-0008), applied here to sources instead of providers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, Protocol, runtime_checkable

from jobhunt_core.errors import SourceFetchError
from jobhunt_core.schemas.job import RawPosting, SearchQuery

if TYPE_CHECKING:
    # Deferred to break the import cycle: agents/base.py's RunContext
    # bundles JobSource instances, so it imports this module at
    # runtime -- this module only needs RunContext for a type
    # annotation, which `from __future__ import annotations` (above)
    # already stores as a string, never evaluated at import time.
    from jobhunt_core.agents.base import RunContext


@runtime_checkable
class JobSource(Protocol):
    """The contract every job source connector implements (api.md §2)."""

    name: ClassVar[str]

    def search(self, query: SearchQuery, ctx: RunContext) -> list[RawPosting]:
        """Return postings matching ``query`` from this source."""
        ...


_SOURCE_REGISTRY: dict[str, type[JobSource]] = {}


def register_source(name: str) -> Callable[[type[JobSource]], type[JobSource]]:
    """Class decorator registering a ``JobSource`` implementation by name.

    The concrete mechanism behind decisions.md ADR-0008 for the source
    layer (api.md §9 Plugin API). ``jobhunt_core.sources`` explicitly
    imports every connector module (rather than a filesystem walk), so
    registration always happens before :func:`get_source_class` is
    called from real code — see final_review.md §1.3.

    Args:
        name: The config-facing source name (e.g. ``"greenhouse"``),
            matching a key under ``sources`` in ``config/sources.yaml``.

    Returns:
        A decorator that registers the class and returns it unchanged.
    """

    def decorator(cls: type[JobSource]) -> type[JobSource]:
        _SOURCE_REGISTRY[name] = cls
        return cls

    return decorator


def available_sources() -> list[str]:
    """Return the sorted names of every currently registered source."""
    return sorted(_SOURCE_REGISTRY)


def get_source_class(name: str) -> type[JobSource]:
    """Look up a registered source class by name.

    Args:
        name: The source name to look up, e.g. ``"greenhouse"``.

    Returns:
        The registered source class (not yet instantiated).

    Raises:
        SourceFetchError: No source is registered under ``name`` —
            usually means ``jobhunt_core.sources`` was never imported,
            or ``config/sources.yaml`` names a source that doesn't
            exist.
    """
    try:
        return _SOURCE_REGISTRY[name]
    except KeyError as exc:
        raise SourceFetchError(
            f"No job source registered under name '{name}'.",
            remedy=(
                f"Available sources: {available_sources()}. Check "
                "config/sources.yaml, and that jobhunt_core.sources "
                "has been imported."
            ),
        ) from exc
