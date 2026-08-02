"""Concrete LLMProvider adapters: Anthropic, OpenAI, and local (Ollama).

Importing this package registers every adapter (decisions.md ADR-0008)
-- an explicit list of imports rather than a filesystem-walk-based
discovery step, so registration is guaranteed to have happened before
any real code calls ``get_provider_class`` (final_review.md §1.3).
"""

from jobhunt_core.llm.providers import (
    anthropic_provider,
    ollama_provider,
    openai_provider,
)

__all__ = ["anthropic_provider", "ollama_provider", "openai_provider"]
