---
description: Prepare interview questions and talking points for a scheduled interview.
---

Generate categorized interview questions with talking points grounded
in the candidate's tailored resume and the posting, once an
application has reached `interview_scheduled` status.

This command is a thin wrapper (decisions.md ADR-0004) — all the actual
logic lives in `jobhunt_core` and `cli/commands/interview.py`, not
here.

1. Ask the user for the `job_posting_id` and the interview type
   (`phone_screen`, `technical`, `onsite`, or `final`) if not already
   given.
2. Run: `python -m cli.main interview <job_posting_id> <interview_type>`
   from the repo root.
3. If the command reports the application isn't in
   `interview_scheduled` status yet, tell the user to record that
   status first via `/outcome` — don't retry blindly.
4. If it reports no tailored resume or no match score exists yet for
   this posting, tell the user those must be generated first (Resume
   Customization / Job Matching) rather than presenting it as an error
   with this command.
5. Present each question with its category and talking points back to
   the user — never a bare question list without the grounding
   (design.md §2).
