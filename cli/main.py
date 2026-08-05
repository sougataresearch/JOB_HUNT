"""jobhunt CLI entry point (design.md §1).

Run from the repo root as a module so ``cli`` resolves as a real
package:

    python -m cli.main setup path/to/cv.pdf
"""

from __future__ import annotations

import typer

from cli.commands.setup import setup_command

app = typer.Typer(help="JOB_HUNT -- local-first AI career assistant.")
app.command(name="setup")(setup_command)


if __name__ == "__main__":
    app()
