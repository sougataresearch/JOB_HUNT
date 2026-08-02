"""Tests for jobhunt_core.config.secrets."""

from jobhunt_core.config.secrets import redact


def test_redact_set_value() -> None:
    """A non-empty value is reported as set without revealing it."""
    assert redact("sk-super-secret") == "<set>"


def test_redact_missing_value() -> None:
    """None or empty values are reported as not set."""
    assert redact(None) == "<not set>"
    assert redact("") == "<not set>"
