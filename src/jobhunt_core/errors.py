"""The shared exception hierarchy every layer raises into (design.md §10).

Phase-1 scope is deliberately limited to the base type. Subtypes
(``ConfigError``, ``LLMProviderError``, ``SourceFetchError``,
``RenderError``, ``StorageError``, ...) are added by the phase that
first needs them (rules.md AI Coding Rule 2), each subclassing
``JobHuntError`` defined here.
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
