"""jobhunt CLI entry point (design.md §1).

Run from the repo root as a module so ``cli`` resolves as a real
package:

    python -m cli.main setup path/to/cv.pdf
    python -m cli.main rank --page 1 --page-size 10
"""

from __future__ import annotations

import typer

from cli.commands.outcome import outcome_command
from cli.commands.rank import rank_command
from cli.commands.setup import setup_command

app = typer.Typer(help="JOB_HUNT -- local-first AI career assistant.")
app.command(name="setup")(setup_command)
app.command(name="rank")(rank_command)
app.command(name="outcome")(outcome_command)


if __name__ == "__main__":
    app()
