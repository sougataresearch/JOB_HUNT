"""Tests for the JobHuntError base type (design.md §10)."""

from jobhunt_core.errors import JobHuntError


def test_error_without_remedy_str() -> None:
    """str() omits the remedy suffix when none was given."""
    err = JobHuntError("something broke")

    assert str(err) == "something broke"
    assert err.remedy == ""


def test_error_with_remedy_str() -> None:
    """str() includes the remedy when one is given."""
    err = JobHuntError("missing key", remedy="set ANTHROPIC_API_KEY")

    assert "missing key" in str(err)
    assert "set ANTHROPIC_API_KEY" in str(err)
