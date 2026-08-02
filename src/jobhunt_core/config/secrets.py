"""Secret-safe display helpers (rules.md §Secrets Management, design.md §9).

``Settings`` (settings.py) never logs field values itself. This module
exists for the rare case something needs to *display* whether a secret
is configured — e.g. a future diagnostic command — without ever
showing the real value.
"""

from __future__ import annotations


def redact(value: str | None) -> str:
    """Return a display-safe stand-in for a secret value.

    Never returns any part of ``value`` — only whether it is set.

    Args:
        value: The secret value, or ``None``/empty if not configured.

    Returns:
        ``"<not set>"`` if ``value`` is falsy, otherwise ``"<set>"``.
    """
    return "<set>" if value else "<not set>"
