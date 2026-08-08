---
name: Feature request
about: Propose a new agent, source connector, template, or capability
title: ""
labels: enhancement
---

**What are you trying to do that JOB_HUNT doesn't support today?**

**Proposed approach**

If this is a new agent or source connector, sketch how it fits the
existing patterns (`agents.md`, `api.md` §2 Job Search API) — a new
agent implementing the `Agent` protocol, or a new `JobSource`
registered via `@register_source`. If it changes an architectural
decision already recorded in `decisions.md`, say which ADR and what
new evidence motivates revisiting it (`rules.md`: don't re-litigate a
settled ADR without new evidence).

**Does this touch anything in `rules.md` AI Coding Rule 1 territory
(generated document content)?**

If your proposal could affect what ends up in a generated resume,
cover letter, or email, confirm it doesn't create a path for
fabricated content — this is the single most important constraint in
this project.

**Would you be willing to implement this yourself?**
