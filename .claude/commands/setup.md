---
description: Parse your CV and create your candidate profile.
---

Run the onboarding flow to build a structured candidate profile from a CV file.

This command is a thin wrapper (decisions.md ADR-0004) — all the actual
logic lives in `jobhunt_core` and `cli/commands/setup.py`, not here.

1. Ask the user for the path to their CV file if they haven't already
   provided one (PDF, DOCX, or Markdown).
2. Run: `python -m cli.main setup <cv_file_path>` from the repo root.
3. Report the resulting profile back to the user: name, number of
   skills extracted, number of experience entries.
4. If the command output notes a missing field (e.g. "email not
   found"), tell the user explicitly rather than assuming the
   extraction fully succeeded — never present a partial extraction as
   complete (rules.md AI Coding Rule 1).
5. If the command fails because a required API key isn't set, tell the
   user which environment variable to add to `.env` (the error message
   will name it) rather than retrying blindly.
