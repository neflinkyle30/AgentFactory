# Design: Agent Factory OSS

## Technical Approach

Greenfield FastAPI + React SPA with a custom Python state machine orchestrating 8 AI phases through DeepSeek API. Each phase is a fresh `query()` call with programmatic gate evaluation. The orchestrator persists all state to PostgreSQL, streams SSE events to the React dashboard, and opens real PRs via abstract Git providers.

## Architecture Decisions

| Decision | Choice | Rejected | Rationale |
|----------|--------|----------|-----------|
| State machine lib | `transitions` (pytransitions) | LangGraph, custom FSM | Guards/conditions map to gates directly; lighter than LangGraph; async support; mature |
| LLM SDK | `openai` Python SDK (DeepSeek-compatible) | dedicated DeepSeek SDK, raw HTTP | OpenAI SDK supports streaming, tools, JSON mode; DeepSeek endpoint is drop-in compatible |
| Real-time | SSE (Server-Sent Events) | WebSockets, polling | Unidirectional (BE→FE), browser-native EventSource with auto-reconnect, simpler than WS |
| Frontend state | @tanstack/react-query + SSE hook | Zustand, Redux | TanStack Query handles cache/invalidation; SSE streaming is ephemeral per-run |
| Database | PostgreSQL (SQLAlchemy + Alembic) | SQLite then migrate | Multi-user from day one requires concurrent writes; SQLite insufficient |
| Git ops | GitPython + provider-specific CLI (gh, glab) | libgit2, raw subprocess | GitPython is battle-tested; `gh` CLI handles auth/tokens natively |
| Auth | JWT (access + refresh tokens) | OAuth2 SSO, session cookies | Stateless; no external provider dependency for MVP; refresh rotation built-in |
| Design system | Hallmark spec → Pencil MCP `.pen` → Tailwind CSS v4 | direct Tailwind, CSS-in-JS | Hallmark enforces anti-AI-generic design; Pencil generates production components |

## Data Flow

```
Ticket Form ──→ POST /api/runs ──→ Intake(G1) ──→ Spec(G2) ──→ Design(G3) ──→ Tasks(G4)
                                         │                                               │
                                    BOUNCED (score<80)                              Develop(G5)
                                         │                                               │
                                    ┌─── SSE ────┐                                 Verify(G6)
                                    │  Dashboard │                                      │
                                    └────────────┘                                 Review(G7)
                                         ▲                                              │
                                    Event Stream ←── Orchestrator ──→ PR(G8) ──→ DONE
                                                                         │
                                                                    Git Provider
                                                                   (gh/glab/bitbucket)
```

Each phase: orchestrator calls `DeepSeekAdapter.query()` → validates output via Pydantic → evaluates gate programmatically → emits SSE event → persists artifact.

## State Machine

States: `INTAKE, SPEC, DESIGN, TASKS, DEVELOP, VERIFY, REVIEW, PR_READY, PR_OPENED, DONE, FAILED, BOUNCED, AWAITING_HITL`

| From | To | Guard | Fail Action |
|------|----|-------|-------------|
| INTAKE | SPEC | G1: score ≥ 80 | BOUNCED |
| SPEC | DESIGN | G2: all ACs covered, schema valid | retry×1 → FAILED |
| DESIGN | TASKS | G3: os.path.exists all files | retry×1 → FAILED |
| TASKS | DEVELOP | G4: all reqs mapped, no circular deps | retry×1 → FAILED |
| DEVELOP | VERIFY | G5: diff≠empty, build=0, lint=0 | retry×2 → FAILED |
| VERIFY | REVIEW | G6: test/AC, suite pass, ≥1 screenshot | loop→DEVELOP×2 → FAILED |
| REVIEW | PR_READY | G7: verdict∈{APPROVED, APPROVED_WITH_SUGGESTIONS} | loop→DEVELOP×2 → FAILED |
| PR_READY | AWAITING_HITL | HITL enabled (config) | pause, await /approve |
| AWAITING_HITL→PR_OPENED | | /approve called | — |
| PR_OPENED | DONE | G8: secret-scan clean, PR created | FAILED |
| ANY | FAILED | budget exhausted OR retries maxed | terminal |

## Data Model

| Entity | Key Fields | Notes |
|--------|-----------|-------|
| **Run** | id(UUID), ticket_ref, status, current_phase, created_at, completed_at, total_cost_usd, budget_limit_usd, retry_counts(JSON), hitl_enabled(bool) | One run per ticket submission |
| **Phase** | run_id(FK), phase_name, status(PENDING/ACTIVE/PASSED/FAILED), started_at, completed_at, retry_count, output(JSON) | One row per phase per run |
| **Artifact** | run_id, phase_name, artifact_type(spec/design/tasks/verify_report/review_report), content_ref(path or text), created_at | Immutable; links to files in `runs/<id>/` |
| **Event** | run_id, seq(int), event_type(phase_start/end/gate_eval/retry/error/budget), payload(JSON), timestamp | Audit trail; append-only |
| **User** | id(UUID), email(unique), password_hash, role(admin/developer/viewer), team_id(FK) | Multi-tenant isolation via team_id |
| **Team** | id(UUID), name, created_at | All resources scoped to team_id |
| **Ticket** | id(UUID), title, description, acceptance_criteria(JSONB), components(JSONB), priority, created_by(FK→User) | Normalized intake output |
| **GitCredential** | user_id(FK), provider(github/gitlab/bitbucket), token(encrypted), remote_url | Per-user Git auth |

## Database Schema (PostgreSQL)

```sql
-- Core tables (Alembic-managed)
CREATE TABLE teams (id UUID PK, name TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE users (id UUID PK, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT DEFAULT 'developer', team_id UUID REFERENCES teams(id), created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE runs (id UUID PK, team_id UUID REFERENCES teams(id), created_by UUID REFERENCES users(id), ticket_ref TEXT, status TEXT NOT NULL DEFAULT 'INTAKE', current_phase TEXT, total_cost_usd NUMERIC(10,6) DEFAULT 0, budget_limit_usd NUMERIC(10,6), hitl_enabled BOOL DEFAULT true, created_at TIMESTAMPTZ DEFAULT now(), completed_at TIMESTAMPTZ);
CREATE TABLE phases (run_id UUID REFERENCES runs(id) ON DELETE CASCADE, phase_name TEXT NOT NULL, status TEXT NOT NULL, started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, retry_count INT DEFAULT 0, output JSONB, PRIMARY KEY (run_id, phase_name));
CREATE TABLE events (id BIGSERIAL, run_id UUID REFERENCES runs(id) ON DELETE CASCADE, seq INT NOT NULL, event_type TEXT NOT NULL, payload JSONB, timestamp TIMESTAMPTZ DEFAULT now(), PRIMARY KEY (run_id, seq));
CREATE TABLE tickets (id UUID PK, run_id UUID REFERENCES runs(id), title TEXT NOT NULL, description TEXT, acceptance_criteria JSONB, components JSONB, priority TEXT, created_by UUID REFERENCES users(id), raw_ticket JSONB, completeness_score INT);

CREATE INDEX idx_runs_team_status ON runs(team_id, status);
CREATE INDEX idx_events_run ON events(run_id, seq);
CREATE INDEX idx_phases_run ON phases(run_id);
```

## API Contracts

| Method | Path | Purpose | Key Schema |
|--------|------|---------|------------|
| POST | `/api/runs` | Submit ticket, start pipeline | `{ticket_source, ticket_key?, form_data?, components[], priority}` → `{run_id, status}` |
| GET | `/api/runs/{id}` | Run status + all phases | `{run, phases[], total_cost_usd, current_phase}` |
| GET | `/api/runs/{id}/stream` | SSE event stream | `text/event-stream`; events: `phase_start`, `phase_end`, `chunk`, `gate_eval`, `error` |
| POST | `/api/runs/{id}/approve` | HITL approval at PR_READY | `{}` → `{status: "APPROVED"}` |
| GET | `/api/runs` | List runs (filterable) | Query: `?status=&team_id=&limit=&offset=` → `{runs[], total}` |
| GET | `/api/runs/{id}/evidence` | Artifact listing | `{tests[], screenshots[], api_responses[], review_report}` |
| POST | `/api/auth/login` | JWT login | `{email, password}` → `{access_token, refresh_token, user}` |
| POST | `/api/auth/refresh` | Refresh JWT | `{refresh_token}` → `{access_token}` |

## DeepSeek Integration Layer

```
DeepSeekAdapter
├── query(system_prompt, messages, tools, output_format, thinking=True) → ResultMessage
├── count_tokens(text) → int
├── calculate_cost(prompt_tokens, completion_tokens) → float  # $0.14/$1.10 per 1M tokens
└── MockAdapter (AGENT_FACTORY_MOCK=1) — deterministic stubs
```

Key concerns: Pydantic `output_format` validation with retry on schema mismatch (max 2). DeepSeek guarantees valid JSON but not schema conformance — fallback to regex extraction of structured fields. Token counting via `tiktoken` (o200k_base encoding). Budget accumulated after each `query()` call.

## Orchestrator Core

```
Orchestrator(run_id, db_session)
├── advance() — evaluate current gate → transition
├── execute_phase(phase_name, role_prompt) — DeepSeekAdapter.query()
├── evaluate_gate(gate_id) — programmatic check
├── handle_failure(reason) — transition to retry or FAILED
└── stream_events() — async generator yielding SSE chunks

PhaseRunner(phase, artifact_store)
└── run(role_config) → PhaseResult

GateEvaluator
├── G1: score = ticket.completeness_score ≥ 80
├── G2: all ACs in spec.coverage_map; spec JSON valid
├── G3: all(path.exists(f) for f in design.files_referenced)
├── G4: all(req in tasks.requirement_map for req in spec.requirements)
├── G5: subprocess.run(["build"]).returncode == 0 AND lint same
├── G6: len(verify.tests) == len(spec.requirements) AND all(test.passed)
├── G7: verify.verdict in ("APPROVED", "APPROVED_WITH_SUGGESTIONS")
└── G8: secret_scan() == clean AND pr_url is not None

ScopeGuard: advisory only — logs warning when Developer edits outside design.components[]
BudgetTracker: accumulates cost after each query; emits warning at 80%, cuts to FAILED at limit (if configured)
```

## Git Provider Abstraction

```python
class GitProvider(ABC):
    def clone(url, path) -> None
    def create_branch(name) -> None
    def commit_all(message) -> None
    def push(branch) -> None
    def create_pr(base, head, title, body) -> str  # returns PR URL

class GitHubProvider(GitProvider):  # uses `gh` CLI
class GitLabProvider(GitProvider):  # uses glab CLI + REST API
class BitbucketProvider(GitProvider):  # uses REST API

def detect_provider(remote_url: str) -> GitProvider:
    # github.com → GitHubProvider, gitlab.com → GitLabProvider, bitbucket.org → BitbucketProvider
```

## Frontend Architecture

```
App (React 19 + Vite + Tailwind CSS v4)
├── AuthProvider (JWT context)
├── Router (/ , /runs, /runs/:id)
│   ├── DashboardPage
│   │   ├── TicketForm (Given-When-Then dynamic rows, validation)
│   │   └── RunList (filterable, SSE badges)
│   └── RunDetailPage
│       ├── PipelineStepper (8 phases, color-coded: green/red/amber/blue)
│       ├── RoleOutputPanel (per-phase streaming text, labeled)
│       ├── EvidencePanel (tabs: Tests | API | Screenshots | Review)
│       ├── BudgetTracker (tokens + cost, progress bar)
│       ├── AuditTrail (chronological event list)
│       └── PRSummaryCard (URL, branch, stats, verdict)
└── DesignSystem (from Pencil MCP .pen files)
    ├── OKLCH palette (anchor hue: deep blue, accent: warm amber, paper: light/dark bands)
    ├── Typography: display (Fraunces/Playfair) + body (Inter/Geist) pair
    ├── ×4 spacing scale (4,8,16,24,32,48,64)
    └── Dark/light mode via CSS custom properties + localStorage
```

SSE hook: `useRunStream(runId)` → subscribes to `/api/runs/{id}/stream`, updates React Query cache on each event. Auto-reconnect with EventSource.

## Auth & Multi-tenancy

JWT access tokens (15min TTL) + refresh tokens (7-day TTL, rotated on use). `Authorization: Bearer <token>` header. All API endpoints require `team_id` derived from JWT claims. Database queries filtered by `team_id` — row-level isolation via application layer (no Postgres RLS for MVP simplicity). Roles: `admin` (manage team, view all), `developer` (submit/approve), `viewer` (read-only).

## Deployment Architecture

```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    env: [DEEPSEEK_API_KEY, DATABASE_URL, JWT_SECRET, AGENT_FACTORY_MOCK]
    ports: ["8000:8000"]
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
  db:
    image: postgres:16-alpine
    volumes: [pgdata:/var/lib/postgresql/data]
    env: [POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD]
```

FastAPI served via uvicorn (dev) / gunicorn+uvicorn (prod). React dev server in dev; `vite build` static files served by nginx/Caddy in prod. Alembic migrations run on startup.

## Security Considerations

| Concern | Mitigation |
|---------|-----------|
| Secret scanning | `detect-secrets` audit before push; G8 gate blocks on detection |
| DeepSeek API key | Environment variable only; never in code/config; .env in .gitignore |
| Jira/auth tokens | Encrypted at rest (Fernet); decrypted at runtime per-request |
| Git provider tokens | Per-user, encrypted; passed to `gh`/`glab` via env vars, never stored in shell history |
| Input validation | Pydantic models on all endpoints; ticket form XSS sanitization |
| SQL injection | SQLAlchemy ORM parameterized queries; no raw SQL |
| CSRF | SameSite=Strict cookies; token in Authorization header (not cookie) |
| Rate limiting | 100 req/min per user via slowapi (FastAPI middleware) |

## Open Questions

- [ ] Jira write-back (status sync) — TBD post-MVP
- [ ] Target repo: one per team config vs. per-run selection? Default: one per team config
- [ ] Review workload guard: this is greenfield — no PR budget risk for initial build
