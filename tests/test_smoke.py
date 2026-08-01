"""Phase 1 smoke test: the package installs and imports cleanly (phases.md Phase 1)."""

import jobhunt_core


def test_package_importable() -> None:
    """jobhunt_core imports without error and exposes a version string."""
    assert jobhunt_core.__version__
