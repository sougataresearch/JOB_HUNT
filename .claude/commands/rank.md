---
description: Show a ranked, paginated shortlist of scored job postings.
---

Show the candidate's postings ranked by match score, one page at a time.

This command is a thin wrapper (decisions.md ADR-0004) — all the actual
logic lives in `jobhunt_core` and `cli/commands/rank.py`, not here.

1. Run: `python -m cli.main rank --page 1 --page-size 10` from the repo
   root (design.md §2 progressive disclosure: default to a summary,
   not everything at once).
2. If the user asks for more results, re-run with `--page 2`, etc. —
   don't dump the full list unless they explicitly ask for it.
3. Report each entry's rank, score, and rationale back to the user —
   never a bare score (design.md §2).
4. If the command reports no active candidate profile, tell the user
   to run `/setup` first rather than retrying blindly.
5. If the ranked list is empty even with an active profile, tell the
   user no postings have been scored yet (Job Matching Agent hasn't
   run) rather than presenting it as an error.
