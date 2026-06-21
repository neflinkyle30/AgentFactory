# Agent Factory OSS — Architecture

## System Overview

Agent Factory automates the ticket-to-PR pipeline. A Jira ticket enters, an AI pipeline of 8 independent roles processes it through 8 hard gates, and a real PR opens against the target repository. No human writes boilerplate.

**Stack**: FastAPI (Python 3.12+) + React 19 (TypeScript) + PostgreSQL 16 + DeepSeek AI

```
┌─────────────┐     SSE Stream      ┌──────────────────────────┐
│  React SPA  │◄────────────────────│     FastAPI Backend      │
│  (Vite)     │                     │                          │
│             │──►POST /api/runs──►│  ┌────────────────────┐  │
│  Dashboard  │                     │  │   Orchestrator     │  │
│  · Stepper  │                     │  │   (State Machine)  │  │
│  · Streaming│                     │  │                    │  │
│  · Evidence │                     │  ├────────────────────┤  │
│  · Budget   │                     │  │ 8 Roles (AI)       │  │
└─────────────┘                     │  │ 8 Gates (Program)  │  │
                                    │  ├────────────────────┤  │
┌─────────────┐                     │  │ DeepSeek Adapter   │──┼──► DeepSeek API
│  PostgreSQL │◄────────────────────│  │ Secret Scanner     │  │
│  (Runs,     │                     │  │ Scope Guard        │  │
│   Phases,   │                     │  │ Budget Tracker     │  │
│   Events)   │                     │  └────────────────────┘  │
└─────────────┘                     └──────────────────────────┘
                                               │
                                    ┌──────────┴──────────┐
                                    │   Git Providers     │
                                    │   · GitHub (gh)     │──► Target Repo
                                    │   · GitLab (glab)   │
                                    │   · Bitbucket (API) │
                                    └─────────────────────┘
```

## Pipeline Flow

```
TICKET ──► INTAKE ──G1──► SPEC ──G2──► DESIGN ──G3──► TASKS ──G4──►
              │                  │               │              │
          BOUNCED            FAILED          FAILED          FAILED
          (score<80)    (retry×1)       (retry×1)       (retry×1)

DEVELOP ──G5──► VERIFY ──G6──► REVIEW ──G7──► PR_READY ──► PR ──G8──► DONE
    │               │               │              │            │
FAILED          LOOP→DEVEL     LOOP→DEVEL    AWAITING_HITL   FAILED
(retry×2)       (loop×2)        (loop×2)     (pause)
```

### State Machine

13 states: `INTAKE, SPEC, DESIGN, TASKS, DEVELOP, VERIFY, REVIEW, PR_READY, PR_OPENED, DONE, FAILED, BOUNCED, AWAITING_HITL`

Powered by the `transitions` library. Each transition is guarded by a programmatic gate that must pass before advancing. Gates evaluate real artifacts (database, filesystem, subprocess exit codes) — not LLM judgment.

### Gate Reference

| Gate | Guard | Pass | Fail |
|------|-------|------|------|
| G1 | Intake → Spec | completeness_score ≥ 80 | BOUNCED |
| G2 | Spec → Design | All ACs covered, schema valid | Retry(×1) → FAILED |
| G3 | Design → Tasks | files_referenced exist | Retry(×1) → FAILED |
| G4 | Tasks → Develop | All reqs mapped, no cycles | Retry(×1) → FAILED |
| G5 | Develop → Verify | diff≠∅, build=0, lint=0 | Retry(×2) → FAILED |
| G6 | Verify → Review | ≥1 test/AC, suite passes | Loop→Develop(×2) |
| G7 | Review → PR | Verdict∈{APPROVED, APPROVED_WITH_SUGGESTIONS} | Loop→Develop(×2) |
| G8 | PR → DONE | Secret-scan clean, PR opened | FAILED |

## Component Architecture

### Backend

```
app/
├── adapters/        # AI provider abstraction
│   ├── base.py      # AIProvider ABC, Message, TokenUsage types
│   ├── deepseek.py  # DeepSeek adapter (OpenAI SDK compatible)
│   ├── mock.py      # MockProvider (AGENT_FACTORY_MOCK=1)
│   └── factory.py   # create_provider() factory
├── api/
│   └── runs.py      # REST endpoints: POST /runs, GET /runs/:id, SSE stream
├── auth/            # JWT auth (login, refresh, middleware)
├── config.py        # pydantic-settings (env vars → typed config)
├── database.py      # Async SQLAlchemy engine + session factory
├── git/             # Git provider abstraction
│   ├── provider.py  # GitProvider ABC + detect_provider()
│   ├── github.py    # GitHubProvider (gh CLI)
│   ├── gitlab.py    # GitLabProvider (glab CLI)
│   └── bitbucket.py # BitbucketProvider (REST API)
├── guards/          # Safety checks
│   └── secret_scan.py # Regex + detect-secrets scanning
├── models/          # SQLAlchemy models (Run, Phase, Ticket, Event...)
│   ├── base.py      # Base + TimestampMixin
│   ├── run.py       # Run (pipeline execution)
│   ├── phase.py     # Phase (per-phase state)
│   ├── ticket.py    # Ticket (normalized intake output)
│   ├── event.py     # Event (immutable audit trail)
│   ├── artifact.py  # Artifact (phase output storage)
│   ├── user.py      # User (auth + team membership)
│   ├── team.py      # Team (multi-tenant isolation)
│   └── git_credential.py # Encrypted Git provider tokens
├── orchestrator/
│   ├── orchestrator.py  # Central execution engine
│   ├── gates.py         # GateEvaluator (G1-G8, programmatic checks)
│   ├── state_machine.py # transitions FSM definition
│   ├── scope_guard.py   # Advisory warnings on out-of-scope edits
│   └── roles/           # 8 AI role implementations
│       ├── intake.py    # Ticket validation + scoring
│       ├── spec.py      # Specification generation
│       ├── design.py    # Technical design + repo exploration
│       ├── tasks.py     # Atomic task breakdown
│       ├── develop.py   # Code implementation
│       ├── verify.py    # Independent test verification
│       ├── review.py    # 5-dimension code review
│       └── pr_agent.py  # PR body generation + metadata
└── schemas/         # Pydantic request/response schemas
```

### Orchestrator → Roles → Gates → State Machine

1. **Orchestrator** receives a ticket via `POST /api/runs`, creates a Run record
2. **Roles** execute sequentially: each role gets a fresh AI session (no shared context)
3. **Gates** evaluate programmatically after each phase (file existence, exit codes, coverage)
4. **State Machine** transitions based on gate results (pass → next phase, fail → retry/Failed)
5. **SSE Stream** emits events at every phase_start, phase_end, gate_eval, and chunk

### Key Design Principles

- **Independent sessions**: Verify and Review receive NO developer context. They see only the ticket, specs, and repo state — just like a human reviewer would.
- **Programmatic gates**: Gates never use LLM judgment. G3 checks `os.path.exists()`, G5 checks subprocess exit codes, G6 counts test results.
- **Advisory scope guard**: Developer edits outside declared components[] log a warning but are NOT denied. The human decides.
- **HITL pause**: Configurable. When enabled, pauses at PR_READY, awaiting manual `/approve` before PR creation.
- **Budget tracking**: Accumulated per-run, no default hard cap in MVP. Displayed in dashboard.

## Database Schema

```
teams        (id, name, created_at)
users        (id, email, password_hash, role, team_id)
runs         (id, team_id, created_by, ticket_ref, status, current_phase,
              total_cost_usd, budget_limit_usd, retry_counts, hitl_enabled, ...)
tickets      (id, run_id, title, description, acceptance_criteria[JSONB],
              components[JSONB], priority, completeness_score, raw_ticket, ...)
phases       (run_id, phase_name, status, started_at, completed_at,
              retry_count, output[JSONB])  — PK: (run_id, phase_name)
events       (id BIGSERIAL, run_id, seq, event_type, payload[JSONB], timestamp)
artifacts    (id, run_id, phase_name, artifact_type, content_ref, created_at)
git_credentials (id, user_id, provider, token_encrypted, remote_url)
```

All queries filtered by `team_id` — multi-tenant isolation at the application layer.

## SSE Streaming Design

```
Client (EventSource)                  Server (FastAPI)
      │                                     │
      │──── GET /api/runs/:id/stream ──────►│
      │                                     │
      │◄── event: phase_start               │ Orchestrator starts phase
      │    data: {"phase":"INTAKE"}         │
      │                                     │
      │◄── event: chunk                     │ AI response chunk
      │    data: {"text":"## Intake..."}    │
      │                                     │
      │◄── event: phase_end                 │ Phase completes
      │    data: {"phase":"INTAKE",         │
      │           "passed":true}            │
      │                                     │
      │◄── event: gate_eval                 │ Gate result
      │    data: {"gate":"g1",              │
      │           "passed":true}            │
      │                                     │
```

Auto-reconnect via EventSource native behavior. Events keyed by `run_id` for multi-run support.

## Deployment

```yaml
docker-compose.yml:
  db:        postgres:16-alpine
  backend:   python:3.12-slim + uvicorn
  frontend:  nginx:alpine (serving vite build output)
```

Frontend proxies `/api/*` to backend:8000 via nginx. SPA fallback (`try_files → index.html`) for React Router.
