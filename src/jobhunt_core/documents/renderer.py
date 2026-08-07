"""DocumentRenderer strategy interface + LaTeX implementation (decisions.md ADR-0007).

Two-step pipeline per ADR-0007: **render** (Jinja2 template + a data
context -> LaTeX source text, with every interpolated value escaped
automatically -- never raw Python/LLM string interpolation into
``.tex``) then **compile** (shell out to a LaTeX engine -> PDF, the
real compiler's log surfaced on failure, design.md §10 "LaTeX compile
failures are first-class, not exceptions to suppress").

Registered via the same decorator-registry pattern as ``LLMProvider``/
``JobSource`` (decisions.md ADR-0008) so a future Markdown/HTML
renderer can be added without touching agent code -- only one
concrete renderer (``"latex"``) exists in v1 (rules.md
no-speculative-abstraction: a second kind isn't built until something
actually needs it).
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable

from jinja2 import Environment

from jobhunt_core.errors import RenderError

_LATEX_ESCAPE_MAP = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_LATEX_ESCAPE_RE = re.compile("|".join(re.escape(char) for char in _LATEX_ESCAPE_MAP))


def latex_escape(value: Any) -> str:
    r"""Escape LaTeX special characters in ``value`` (tasks.md T11.1 checklist).

    Set as the Jinja2 environment's ``finalize`` hook below, so every
    ``\VAR{...}`` substitution is escaped automatically -- a template
    author cannot forget it, and candidate/posting data can never
    break LaTeX syntax or (worse) inject arbitrary LaTeX commands.
    """
    if value is None:
        return ""
    return _LATEX_ESCAPE_RE.sub(lambda match: _LATEX_ESCAPE_MAP[match.group()], str(value))


def _latex_jinja_env() -> Environment:
    r"""A Jinja2 environment whose delimiters don't collide with LaTeX's own ``{}`` syntax.

    Standard LaTeX+Jinja2 pattern (the default ``{{ }}``/``{% %}``
    delimiters are unusable -- LaTeX uses bare ``{`` ``}`` constantly
    for grouping/arguments): ``\VAR{...}`` for variables,
    ``\BLOCK{...}`` for control flow, ``%#`` for template-only
    comments not rendered into the ``.tex`` source.
    """
    # autoescape=False: Jinja2's autoescape is HTML-oriented; latex_escape
    # (set as finalize below) is the LaTeX-appropriate replacement.
    return Environment(
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
        line_comment_prefix="%#",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        finalize=latex_escape,
    )


@runtime_checkable
class DocumentRenderer(Protocol):
    """The contract every document renderer implements (design.md §4 Component Hierarchy)."""

    kind: ClassVar[str]

    def render(self, template_source: str, context: dict[str, Any]) -> str:
        """Render ``template_source`` (a Jinja2 template) with ``context`` into source text."""
        ...

    def compile(self, source: str, output_dir: Path, *, base_name: str) -> Path:
        """Compile source text into a PDF under ``output_dir``, named ``<base_name>.pdf``."""
        ...


_RENDERER_REGISTRY: dict[str, type[DocumentRenderer]] = {}


def register_renderer(kind: str) -> Callable[[type[DocumentRenderer]], type[DocumentRenderer]]:
    """Class decorator registering a ``DocumentRenderer`` implementation by ``kind``."""

    def decorator(cls: type[DocumentRenderer]) -> type[DocumentRenderer]:
        _RENDERER_REGISTRY[kind] = cls
        return cls

    return decorator


def available_renderers() -> list[str]:
    """Return the sorted names of every currently registered renderer kind."""
    return sorted(_RENDERER_REGISTRY)


def get_renderer_class(kind: str) -> type[DocumentRenderer]:
    """Look up a registered renderer class by kind.

    Raises:
        RenderError: No renderer is registered under ``kind``.
    """
    try:
        return _RENDERER_REGISTRY[kind]
    except KeyError as exc:
        raise RenderError(
            f"No document renderer registered under kind '{kind}'.",
            remedy=f"Available renderers: {available_renderers()}.",
        ) from exc


@register_renderer("latex")
class LaTeXRenderer:
    """``DocumentRenderer`` over a system LaTeX engine (decisions.md ADR-0007: lualatex/xelatex)."""

    kind: ClassVar[str] = "latex"

    def __init__(
        self,
        *,
        engine: str = "lualatex",
        timeout_s: float = 30.0,
        run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        """Construct the renderer.

        Args:
            engine: The LaTeX engine binary to invoke (ADR-0007 names
                lualatex/xelatex; lualatex is the default -- verified
                working in this project's dev environment).
            timeout_s: Compile timeout ceiling (config.md §Timeouts: 30s).
            run: Injectable ``subprocess.run``-shaped callable, so
                tests can fake a compile without needing to reason
                about a specific fake LaTeX binary (real compiles are
                still exercised by dedicated tests that don't inject this).
        """
        self._engine = engine
        self._timeout_s = timeout_s
        self._run = run

    def render(self, template_source: str, context: dict[str, Any]) -> str:
        """See ``DocumentRenderer.render``."""
        return _latex_jinja_env().from_string(template_source).render(**context)

    def compile(self, source: str, output_dir: Path, *, base_name: str) -> Path:
        """See ``DocumentRenderer.compile``.

        Raises:
            RenderError: The engine exited non-zero, produced no PDF,
                or exceeded ``timeout_s`` -- the actual LaTeX log is
                included in the message, never silently suppressed
                (design.md §10).
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        tex_filename = f"{base_name}.tex"
        (output_dir / tex_filename).write_text(source, encoding="utf-8")

        try:
            result = self._run(
                [self._engine, "-interaction=nonstopmode", "-halt-on-error", tex_filename],
                cwd=output_dir,
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise RenderError(
                f"LaTeX compilation of '{tex_filename}' exceeded the {self._timeout_s}s timeout.",
                remedy="Simplify the template, or investigate a hang (config.md §Timeouts).",
            ) from exc

        pdf_path = output_dir / f"{base_name}.pdf"
        if result.returncode != 0 or not pdf_path.exists():
            log_path = output_dir / f"{base_name}.log"
            log_text = (
                log_path.read_text(encoding="utf-8", errors="replace")
                if log_path.exists()
                else f"{result.stdout}\n{result.stderr}"
            )
            raise RenderError(
                f"LaTeX compilation failed for '{tex_filename}' (exit code {result.returncode}).\n"
                f"{log_text[-4000:]}",
                remedy="Check the LaTeX log above for the exact error and fix the template.",
            )
        return pdf_path
