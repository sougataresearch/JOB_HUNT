"""Tests for the agent registry (final_review.md §1.3 mitigation)."""

import pytest

from jobhunt_core.errors import JobHuntError
from jobhunt_core.orchestration.registry import _AGENT_REGISTRY, available_agents, get_agent_class


@pytest.fixture(autouse=True)
def _clean_registry():
    """Snapshot and restore the module-level registry around each test."""
    original = dict(_AGENT_REGISTRY)
    yield
    _AGENT_REGISTRY.clear()
    _AGENT_REGISTRY.update(original)


def test_importing_agents_package_registers_resume_analysis() -> None:
    """Importing jobhunt_core.agents registers the resume_analysis agent (T5.2)."""
    import jobhunt_core.agents  # noqa: F401

    assert "resume_analysis" in available_agents()


def test_get_agent_class_returns_resume_analysis_agent() -> None:
    """The registry resolves 'resume_analysis' to the correct concrete class."""
    import jobhunt_core.agents  # noqa: F401
    from jobhunt_core.agents.resume_analysis_agent import ResumeAnalysisAgent

    assert get_agent_class("resume_analysis") is ResumeAnalysisAgent


def test_get_agent_class_unregistered_raises_with_remedy() -> None:
    """Looking up an unregistered agent name raises JobHuntError with a remedy."""
    with pytest.raises(JobHuntError) as exc_info:
        get_agent_class("does-not-exist")

    assert "does-not-exist" in str(exc_info.value)
    assert exc_info.value.remedy
