---
description: Generate the static HTML career analytics dashboard.
---

Generate an offline HTML dashboard summarizing response, interview,
and offer rates across all tracked applications, broken down by role
and by source.

This command is a thin wrapper (decisions.md ADR-0004) — all the actual
logic lives in `jobhunt_core` and `cli/commands/report.py`, not here.

1. Run: `python -m cli.main report` from the repo root (writes to
   `<data_dir>/report.html` by default; pass `--output <path>` to
   write elsewhere).
2. Tell the user where the file was written and that it opens directly
   in a browser — no server, no network calls (design.md §1).
3. If the report shows "not enough data" (fewer than 5 submitted
   applications), tell the user that plainly rather than reading the
   0% rates as real signal — the dashboard withholds rates below that
   threshold specifically to avoid that misread (agents.md §11 Failure
   handling).
