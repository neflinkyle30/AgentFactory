# Tasks: Agent Factory OSS

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

| Unit | Goal | PR | Lines |
|------|------|----|-------|
| 1 | Backend scaffold + DB + DeepSeek adapter | PR 1 | ~250 |
| 2 | Orchestrator + Intake + SSE + Auth | PR 2 | ~300 |
| 3 | Develop agent + G5 + scope guard | PR 3 | ~250 |
| 4 | Frontend scaffold + Design tokens | PR 4 | ~350 |
| 5 | Dashboard components (form, stepper, streaming) | PR 5 | ~300 |

## MVP-0: Foundation — 2 roles (Intake, Develop), 2 gates (G1, G5)

### Backend
- [x] **T-001** FastAPI scaffold + config: `backend/`, `pyproject.toml`, `requirements.txt`, `main.py`, `config.py`. **S·BE·0 deps**
- [x] **T-002** SQLAlchemy models: Run, Phase, Ticket, Event, User, Team, GitCredential in `backend/models/`. **M·BE·T-001**
- [x] **T-003** Alembic migrations for all tables + seed team/user. **S·BE·T-002**
- [x] **T-004** `backend/adapters/deepseek.py`: OpenAI SDK query(), streaming, thinking=true, tiktoken counting, cost calc. + MockAdapter for `AGENT_FACTORY_MOCK=1`. **L·BE·T-001**
- [x] **T-005** `backend/orchestrator/state_machine.py`: `transitions` lib, 13 states, G1/G5 guards, retry counters. **M·BE·T-002**
- [x] **T-006** `backend/orchestrator/gates.py`: G1 (score≥80), G5 (subprocess build=0 + lint=0). Programmatic only. **M·BE·T-005·ORCH-REQ-6**
- [x] **T-007** `backend/roles/intake.py`: rubric scorer (AC 40, desc 25, title 15, priority 10, components 10pts), canonical JSON normalize, BOUNCED response with missing[]+suggestions[]. **L·BE·T-006·INTAKE-REQ-1→7**
- [x] **T-008** `POST /api/runs` + `GET /api/runs/{id}`: Pydantic validation, creates Run+Ticket, triggers orchestrator. **M·BE·T-007**
- [x] **T-009** `GET /api/runs/{id}/stream`: `text/event-stream`, emits phase_start/end, chunk, gate_eval, error keyed by run_id. **M·BE·T-005·ORCH-REQ-5**
- [x] **T-010** `backend/orchestrator/core.py`: advance(), execute_phase(), handle_failure() with retry budgets, SSE emit, artifact persist. **L·BE·T-005,T-004,T-006·ORCH-REQ-1,2,3**
- [x] **T-011** `backend/roles/develop.py`: clone to `runs/<id>/workdir`, branch `agent-factory/<ticket>`, task-by-task edits via DeepSeek, token/cost tracking. **L·BE·T-010·DEVL-REQ-1→8**
- [x] **T-012** `backend/guards/scope.py`: advisory warn-only on edits outside `components[]`, logs file+line+context. **S·BE·T-011**
- [x] **T-013** `backend/auth/`: JWT login/refresh, Bearer middleware, bcrypt hash, team_id from claims. **M·BE·T-002**

### Frontend
- [x] **T-014** React+Vite+Tailwind v4 scaffold: `frontend/`, Router, @tanstack/react-query. **S·FE·0**
- [x] **T-015** `AuthProvider.tsx` + `LoginPage.tsx`: JWT context, login/refresh/logout, protected routes. **M·FE·T-013,T-014**
- [x] **T-016** Router + layout shell: `/login`, `/runs`, `/runs/:id`. **S·FE·T-015**
- [x] **T-017** `TicketFormPage.tsx`: title, description, dynamic Given-When-Then rows, priority, components, validation, POST. **M·FE·T-008·DASH-REQ-6**
- [x] **T-018** `PipelineStepper.tsx`: 8 phases (Intake→PR), status colors (green/cyan/red/gray), compact variant. **M·FE·T-009·DASH-REQ-1**
- [x] **T-019** `useRunStream.ts`: Verified — correct SSE connection, cache invalidation, auto-reconnect. Minor dead-code finding (handlersRef unused). **M·FE·T-009·DASH-REQ-2,12**
- [x] **T-020** `RunDetailPage.tsx`: stepper + per-phase streaming output panel + gate status + phase list. **L·FE·T-018,T-019·DASH-REQ-3**
- [x] **T-021** `DashboardPage.tsx`: Blueprint grid background, stats row, run table with status symbols, edge marks, FIG annotation, footer. **M·FE·T-017**

### Design System
- [x] **T-022** `design/design-system.md`: OKLCH palette (anchor blue, accent amber), Fraunces+Inter type pair, ×4 spacing, asymmetric layout rules. **M·DS·0**
- [x] **T-023** `design/wireframes.pen`: Pencil MCP wireframes for dashboard layout + ticket form, light mode. **M·DS·T-022**
- [x] **T-024** `frontend/src/styles/tokens.css`: CSS custom properties from design spec, Tailwind v4 config consuming tokens. **M·FE·T-014,T-022**

## Phase-1: Complete Pipeline — 8 roles, 8 gates

- [ ] **T-025** `backend/roles/spec.py`: SHALL reqs + Given-When-Then scenarios, 100% AC coverage. G2 validates all ACs mapped + schema valid. **L·BE·T-010·SPEC-REQ-1→7**
- [ ] **T-026** `backend/roles/design.py`: read-only repo exploration (Glob/Grep/Read), design.md + files_referenced[]. G3 validates os.path.exists(). **L·BE·T-010·DESIGN-REQ-1→9**
- [ ] **T-027** `backend/roles/tasks.py`: atomic breakdown, requirement-to-task coverage, circular dep detection. G4 validates coverage + no cycles. **L·BE·T-010·TASKS-REQ-1→7**
- [ ] **T-028** `backend/roles/verify.py`: fresh session, test-per-AC, Playwright screenshot, API capture, evidence to `runs/<id>/evidence/`. **L·BE·T-010·VERF-REQ-1→8**
- [ ] **T-029** `backend/roles/review.py`: 5-dimension review (Security>Integrity>Performance>Architecture>Quality), CRITICAL/WARNING/SUGGESTION/OK. Read-only. **L·BE·T-010·REVW-REQ-1→9**
- [ ] **T-030** `backend/roles/pr_agent.py`: secret scan pre-push, GitProvider dispatch, auto-generated PR body. **L·BE·T-010·PR-REQ-1→8**
- [ ] **T-031** `backend/git/provider.py`: GitProvider ABC (clone,branch,commit,push,create_pr) + detect_provider(). GitHub stub. **M·BE·T-030**
- [ ] **T-032** Expand to 8-phase PipelineStepper. Add EvidencePanel (Tests|API|Screenshots|Review tabs), BudgetTracker, PRSummaryCard. Orchestrator loop G6↔G7. **L·FE·T-020,T-028,T-029·DASH-REQ-1→5,9**
- [ ] **T-033** HITL pause: `POST /api/runs/{id}/approve` + HITLApprove component. Pause at PR_READY until approved. **M·BE+FE·T-030·ORCH-REQ-7**
- [ ] **T-034** Dark mode: `dark.css` with OKLCH dark variants, theme toggle, localStorage persistence, transitions. Add to G5/G6/G7 gate evaluator chains (retry×2 + loop×2). **M·FE·T-024·DASH-REQ-8**

## Phase-2: Polish + Providers

- [ ] **T-035** `backend/git/github.py`: GitHubProvider via `gh` CLI. **M·BE·T-031**
- [ ] **T-036** `backend/git/gitlab.py`: GitLabProvider via glab CLI + REST API. **M·BE·T-031**
- [ ] **T-037** `backend/git/bitbucket.py`: BitbucketProvider via REST API. **M·BE·T-031**
- [ ] **T-038** `backend/guards/secret_scan.py`: detect-secrets audit, block push + FAIL run on detection. **M·BE·T-030·PR-REQ-1**
- [ ] **T-039** Full Pencil MCP dashboard: all components from `.pen` with pixel-accurate rendering. **L·FE·T-023,T-024**

## Phase-3: Hardening

- [ ] **T-040** Add pytest, mypy, ruff configs to `pyproject.toml`. Write GateEvaluator unit tests (`tests/test_gates.py`). **M·BE·T-006,T-025→T-030**
- [ ] **T-041** Integration test: full pipeline happy path (`tests/test_pipeline.py`, mock mode). Frontend component tests via Vitest. **L·BE+FE·T-020,T-032**
- [ ] **T-042** `docker-compose.yml` + `backend/Dockerfile` + `frontend/Dockerfile` + `nginx.conf`. **M·DO·T-001,T-014**
- [ ] **T-043** Docs: `docs/architecture.md`, `docs/setup.md`, `docs/roles.md`. **M·DOC·T-042**
