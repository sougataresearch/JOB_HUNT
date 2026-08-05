"""The shared exception hierarchy every layer raises into (design.md §10).

Subtypes are added by the phase that first needs them (rules.md AI
Coding Rule 2), each subclassing ``JobHuntError`` defined here.
Remaining subtypes (``SourceFetchError``, ``RenderError``, ...) arrive
in later phases.
"""

from __future__ import annotations


class JobHuntError(Exception):
    """Base class for every exception raised by jobhunt_core.

    Every user-facing error carries a ``remedy``: a short, actionable
    string telling the user what to do about it (design.md §10), e.g.
    "ANTHROPIC_API_KEY is not set — add it to your .env file".

    Args:
        message: Human-readable description of what went wrong.
        remedy: Actionable next step for the user. Defaults to an
            empty string when no specific remedy applies.
    """

    def __init__(self, message: str, *, remedy: str = "") -> None:
        """Store the message and optional remedy for later display."""
        super().__init__(message)
        self.message = message
        self.remedy = remedy

    def __str__(self) -> str:
        """Return the message, with the remedy appended if one was given."""
        if self.remedy:
            return f"{self.message} (remedy: {self.remedy})"
        return self.message


class ConfigError(JobHuntError):
    """Raised when configuration is missing, invalid, or inconsistent.

    E.g. an enabled agent references a provider whose API key
    environment variable is not set (config.md §Config Validation
    Rules, phases.md Phase 2 acceptance criteria).
    """


class LLMProviderError(JobHuntError):
    """Raised when an LLM provider call fails in a way callers must handle.

    Covers: the shared retry policy (design.md §11) being exhausted, a
    non-retryable provider error (auth, bad request, content policy),
    an unregistered provider name (api.md §9 Plugin API), or a
    provider returning output that does not satisfy a requested
    structured-output schema (rules.md AI Coding Rule 1 territory —
    never silently invent a parsed result).
    """


class UnsupportedFormatError(JobHuntError):
    """Raised when no registered CV parser supports a given file (api.md §1)."""


class StorageError(JobHuntError):
    """Raised for storage-layer failures a repository cannot recover from.

    E.g. saving/updating a row by id that does not exist (design.md
    §10's typed exception hierarchy).
    """
