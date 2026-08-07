---
description: Record a status change for a tracked application.
---

Record an application's status transition (e.g. after a recruiter
reply, an interview invite, or a rejection).

This command is a thin wrapper (decisions.md ADR-0004) — all the actual
logic lives in `jobhunt_core` and `cli/commands/outcome.py`, not here.

1. Ask the user for the `job_posting_id` and the new status if not
   already given. Valid statuses: `drafted`, `submitted`, `screening`,
   `interview_scheduled`, `interview_completed`, `offer`, `rejected`,
   `withdrawn`.
2. Run: `python -m cli.main outcome <job_posting_id> <status> --note "<optional note>"`
   from the repo root.
3. If the command reports no job posting or no application exists yet
   for that posting, tell the user rather than retrying blindly — an
   application must already be created before an outcome can be
   recorded against it.
4. Confirm the new status back to the user after a successful update
   (design.md §2: never a bare confirmation without the actual new
   state).
