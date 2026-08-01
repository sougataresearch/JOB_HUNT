# Folder Structure — JOB_HUNT

Status: Draft v1.0 · Last updated: 2026-08-02

Full annotated tree for the target production layout. This is what
Phase 1 (`phases.md`, `tasks.md` T1.4) scaffolds. Every directory's
purpose is stated so an AI coding agent can place new files correctly
without guessing.

```
JOB_HUNT/
├── .claude/
│   ├── commands/                    # Thin slash-command wrappers (decisions.md ADR-0004)
│   │   ├── setup.md                 # Onboarding: CV → CandidateProfile
│   │   ├── scrape.md                # Job Search Agent trigger
│   │   ├── rank.md                  # Ranking view
│   │   ├── apply.md                 # Full per-posting pipeline
│   │   ├── outcome.md               # Record application status change
│   │   ├── interview.md             # Interview Prep trigger
│   │   └── html-report.md           # Career Analytics dashboard generation
│   └── skills/                      # Claude Code skills (e.g., portal-specific search CLIs)
│       └── <portal_name>/SKILL.md
│
├── src/
│   └── jobhunt_core/                 # The importable, independently testable core (ADR-0004)
│       ├── __init__.py
│       ├── logging_config.py         # design.md §9
│       ├── errors.py                 # JobHuntError hierarchy, design.md §10
│       │
│       ├── config/                   # config.md — zero internal deps
│       │   ├── settings.py           # Settings (pydantic-settings), layered loading
│       │   └── secrets.py
│       │
│       ├── schemas/                  # Shared Pydantic vocabulary — zero internal deps
│       │   ├── profile.py            # CandidateProfile
│       │   ├── job.py                # JobPosting, SearchQuery, RawPosting
│       │   ├── match.py              # MatchScore
│       │   ├── ats.py                # ATSReport
│       │   ├── application.py        # Application, ApplicationEvent
│       │   ├── interview.py          # InterviewPrepPack, InterviewQuestion
│       │   ├── skill_gap.py          # SkillGapReport
│       │   ├── email.py              # EmailDraft
│       │   └── analytics.py          # AnalyticsReport
│       │
│       ├── llm/                      # decisions.md ADR-0003, api.md §5
│       │   ├── provider.py           # LLMProvider Protocol
│       │   ├── retry.py              # Shared backoff policy
│       │   ├── types.py              # LLMResponse, StructuredLLMResponse
│       │   └── providers/
│       │       ├── anthropic_provider.py
│       │       ├── openai_provider.py
│       │       └── ollama_provider.py
│       │
│       ├── storage/                  # database.md, api.md §7
│       │   ├── db.py                 # engine/session setup
│       │   ├── models/               # SQLAlchemy models, 1:1 with database.md tables
│       │   │   ├── profile.py
│       │   │   ├── job.py
│       │   │   ├── application.py
│       │   │   ├── interview.py
│       │   │   ├── template.py
│       │   │   └── agent_run.py
│       │   └── repositories/
│       │       ├── profile_repo.py
│       │       ├── job_repo.py
│       │       ├── match_repo.py
│       │       ├── application_repo.py
│       │       └── interview_repo.py
│       │
│       ├── documents/                # decisions.md ADR-0006, ADR-0007
│       │   ├── parsers/              # CV ingestion, api.md §1
│       │   │   ├── pdf.py
│       │   │   ├── docx.py
│       │   │   └── markdown.py
│       │   ├── renderer.py           # DocumentRenderer strategy interface
│       │   ├── verify.py             # PDF text-extraction ATS verification
│       │   └── report_renderer.py    # HTML dashboard generator
│       │
│       ├── sources/                  # api.md §2 — job board/API connectors
│       │   ├── base.py               # JobSource Protocol + register_source
│       │   ├── manual_import_source.py
│       │   └── <provider>_source.py
│       │
│       ├── prompts/                  # api.md §4 — loader only; templates live in prompts/library (below)
│       │   └── loader.py
│       │
│       ├── agents/                   # One file per agent — agents.md
│       │   ├── base.py               # Agent Protocol, register_agent, RunContext, AgentResult
│       │   ├── resume_analysis_agent.py
│       │   ├── skill_gap_agent.py
│       │   ├── job_search_agent.py
│       │   ├── job_matching_agent.py
│       │   ├── ats_optimization_agent.py
│       │   ├── resume_customization_agent.py
│       │   ├── cover_letter_agent.py
│       │   ├── email_agent.py
│       │   ├── application_tracking_agent.py
│       │   ├── interview_prep_agent.py
│       │   └── career_analytics_agent.py
│       │
│       └── orchestration/            # architecture.md §6
│           ├── registry.py           # AgentRegistry
│           ├── pipeline.py           # Sequential staged pipeline (decisions.md ADR-0005)
│           └── ranking.py            # api.md §3
│
├── prompts/
│   └── library/                      # Versioned prompt templates — prompts.md
│       ├── resume_analysis/extract_profile/1.0.md
│       ├── skill_gap/analyze/1.0.md
│       ├── job_matching/score/1.0.md
│       ├── ats/analyze/1.0.md
│       ├── resume_customization/draft/1.0.md
│       ├── resume_customization/review/1.0.md
│       ├── cover_letter/draft/1.0.md
│       ├── email/draft/1.0.md
│       ├── interview/prepare/1.0.md
│       └── career_analytics/summarize/1.0.md
│
├── documents/
│   └── templates/                    # design.md §7 — LaTeX/Jinja2 sources
│       ├── registry.yaml             # template metadata (database.md §14)
│       ├── resume/
│       │   └── moderncv_default.tex.jinja
│       └── cover_letter/
│           └── default.tex.jinja
│
├── cli/                               # design.md §1 — scriptable entry point (Typer)
│   ├── main.py
│   └── commands/
│       ├── setup.py
│       ├── scrape.py
│       ├── rank.py
│       ├── apply.py
│       ├── outcome.py
│       └── report.py
│
├── config/                            # config.md — committed, no secrets
│   ├── llm.yaml
│   ├── agents.yaml
│   ├── sources.yaml
│   └── local.yaml.example             # copy to local.yaml (gitignored) for personal overrides
│
├── migrations/                        # Alembic
│   ├── env.py
│   └── versions/
│
├── data/                              # Entirely gitignored — real user data
│   ├── raw/                           # raw scraped HTML/JSON per posting
│   ├── documents/                     # generated PDFs/LaTeX, one dir per application
│   ├── logs/
│   └── jobhunt.db                     # SQLite file
│
├── tests/                             # Mirrors src/jobhunt_core 1:1
│   ├── agents/
│   ├── llm/
│   ├── storage/
│   ├── documents/
│   ├── sources/
│   ├── orchestration/
│   ├── integration/
│   ├── e2e/
│   ├── eval/                          # AI evaluation golden-file cases (testing.md §3)
│   ├── performance/
│   └── fixtures/
│       ├── cvs/
│       ├── postings/
│       └── cassettes/
│
├── .github/
│   ├── workflows/ci.yml
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
│
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── pyproject.toml
├── LICENSE                            # added in Phase 18, decisions.md ADR-0009
├── README.md
├── CONTRIBUTING.md                    # added in Phase 18
│
└── (this documentation suite, at repo root)
    PRD.md  architecture.md  design.md  decisions.md  phases.md
    rules.md  memory.md  tasks.md  api.md  database.md  agents.md
    prompts.md  config.md  testing.md  roadmap.md  folder_structure.md
    implementation_order.md  final_review.md  progress_log.md
```

## Rationale for Key Placements

- **`src/` layout, not flat**: prevents accidental imports of
  uninstalled package code, standard modern Python packaging practice
  (`rules.md` §Coding Conventions).
- **`prompts/library/` outside `src/`**: prompts are content/data
  (versioned Markdown), not code — keeping them outside the Python
  package tree makes them easy to browse/diff/contribute to without
  touching Python (`PRD.md` §7 open-source-readiness).
- **`documents/templates/` outside `src/`**: same reasoning — LaTeX
  templates are content contributors edit without touching Python
  (`roadmap.md` §6-month horizon: community-contributed CV template).
- **`data/` fully gitignored, sibling to `src/`**: keeps the repo
  clean of personal data by construction — a `git status` accidentally
  showing a real CV is structurally hard to do (`rules.md` §Secrets
  Management).
- **`.claude/` at repo root**: Claude Code convention — commands/skills
  must live here to be discovered (`architecture.md` §1).
- **Documentation suite at repo root, not `docs/`**: matches this
  workspace's own established convention
  (`sougata_solver`'s `rules.md`/`phases.md`/etc. at repo root) —
  keeps the docs the very first thing anyone (human or AI agent) sees
  when opening the repo.
