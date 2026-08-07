"""Tests for DocumentRenderer/LaTeXRenderer (tasks.md T11.1).

Compiles real LaTeX via the actual system engine (this dev environment
has MiKTeX installed and verified working) -- this is a local,
deterministic, offline compiler invocation, not a live network/LLM
call, so testing.md's "no live calls" rule doesn't apply to it, and
running it for real is the only way to actually verify "compiles
without manual intervention on a clean LaTeX install" (phases.md
Phase 11 AC), matching how tests/migrations/test_alembic.py runs real
Alembic commands instead of mocking them.
"""

from pathlib import Path

import pytest

from jobhunt_core.documents.renderer import (
    _RENDERER_REGISTRY,
    LaTeXRenderer,
    available_renderers,
    get_renderer_class,
    latex_escape,
    register_renderer,
)
from jobhunt_core.errors import RenderError

_MINIMAL_TEMPLATE = r"""\documentclass{article}
\begin{document}
\VAR{content}
\end{document}
"""


class _FakeRenderer:
    """A minimal DocumentRenderer-shaped class used only to test the registry."""

    kind = "fake"

    def render(self, template_source, context):
        raise NotImplementedError

    def compile(self, source, output_dir, *, base_name):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _clean_registry():
    """Snapshot and restore the module-level registry around each test."""
    original = dict(_RENDERER_REGISTRY)
    yield
    _RENDERER_REGISTRY.clear()
    _RENDERER_REGISTRY.update(original)


def test_register_renderer_adds_to_registry() -> None:
    """The decorator registers the class under the given kind unchanged."""
    decorated = register_renderer("fake")(_FakeRenderer)

    assert decorated is _FakeRenderer
    assert "fake" in available_renderers()
    assert get_renderer_class("fake") is _FakeRenderer


def test_get_renderer_class_unregistered_raises_render_error() -> None:
    """Looking up an unregistered kind raises RenderError with a remedy."""
    with pytest.raises(RenderError) as exc_info:
        get_renderer_class("does-not-exist")

    assert exc_info.value.remedy


def test_latex_is_registered_by_default() -> None:
    """Importing jobhunt_core.documents registers LaTeXRenderer."""
    import jobhunt_core.documents  # noqa: F401 -- triggers registration

    assert "latex" in available_renderers()
    assert get_renderer_class("latex") is LaTeXRenderer


# ---- latex_escape: tasks.md T11.1 checklist fixture (&, %, _, #) ----


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("A & B", r"A \& B"),
        ("50% done", r"50\% done"),
        ("user_id", r"user\_id"),
        ("C# developer", r"C\# developer"),
        ("$100", r"\$100"),
        ("a{b}c", r"a\{b\}c"),
        ("a~b", r"a\textasciitilde{}b"),
        ("a^b", r"a\textasciicircum{}b"),
        ("back\\slash", r"back\textbackslash{}slash"),
    ],
)
def test_latex_escape_handles_every_special_character(raw: str, expected: str) -> None:
    """Known fixture: every LaTeX special character is escaped correctly."""
    assert latex_escape(raw) == expected


def test_latex_escape_none_returns_empty_string() -> None:
    """A None value (e.g. an unset optional field) renders as empty, not the string 'None'."""
    assert latex_escape(None) == ""


def test_render_applies_escaping_to_variables_not_template_syntax() -> None:
    """Static \\BLOCK{}/\\VAR{} template syntax is untouched; only interpolated data is escaped."""
    renderer = LaTeXRenderer()
    template = r"""\documentclass{article}
\begin{document}
\BLOCK{if show}\VAR{content}\BLOCK{endif}
\end{document}
"""

    tex = renderer.render(template, {"show": True, "content": "100% & more"})

    assert r"\begin{document}" in tex  # static syntax untouched
    assert r"100\% \& more" in tex  # data escaped


# ---- Real LaTeX compilation ----


def test_compile_produces_a_real_pdf(tmp_path: Path) -> None:
    """A minimal document compiles cleanly with the real system LaTeX engine."""
    renderer = LaTeXRenderer()
    tex = renderer.render(_MINIMAL_TEMPLATE, {"content": "Hello, world!"})

    pdf_path = renderer.compile(tex, tmp_path, base_name="doc")

    assert pdf_path == tmp_path / "doc.pdf"
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_compile_escapes_special_characters_without_breaking_compilation(tmp_path: Path) -> None:
    """phases.md Phase 11 AC: malformed/special LaTeX characters never break compilation."""
    renderer = LaTeXRenderer()
    dangerous_content = "AT&T's 100% guarantee: user_id #1 costs $5 {not a group}"
    tex = renderer.render(_MINIMAL_TEMPLATE, {"content": dangerous_content})

    pdf_path = renderer.compile(tex, tmp_path, base_name="doc")

    assert pdf_path.exists()


def test_compile_failure_raises_render_error_with_the_actual_log(tmp_path: Path) -> None:
    """design.md §10: a LaTeX compile failure surfaces the real log, not a generic message."""
    renderer = LaTeXRenderer()
    broken_tex = r"\documentclass{article}\begin{document}\undefinedcommandxyz\end{document}"

    with pytest.raises(RenderError) as exc_info:
        renderer.compile(broken_tex, tmp_path, base_name="broken")

    assert "undefinedcommandxyz" in str(exc_info.value) or "Undefined control sequence" in str(
        exc_info.value
    )


def test_compile_timeout_raises_render_error(tmp_path: Path) -> None:
    """A compile exceeding the timeout ceiling raises RenderError, not hanging (config.md)."""
    import subprocess

    def _always_times_out(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="lualatex", timeout=0.01)

    renderer = LaTeXRenderer(timeout_s=0.01, run=_always_times_out)

    with pytest.raises(RenderError, match="timeout"):
        renderer.compile("irrelevant", tmp_path, base_name="doc")
