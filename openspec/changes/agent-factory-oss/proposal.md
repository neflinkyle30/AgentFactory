# Proposal: Agent Factory OSS

## Intent

Automate the ticket-to-PR pipeline for an internal development team. A Jira ticket enters, an AI pipeline of six independent roles (Intake → Architect → Developer → Tester → Reviewer → PR) processes it, six hard gates validate quality at each stage, and a real PR opens against the target repo. No human writes a line of boilerplate code.

## Scope

### In Scope
- 6-role AI pipeline with 6 hard gates (fail, don't warn)
- Multi-user web app: FastAPI backend + React SPA + PostgreSQL
- DeepSeek API with thinking mode on all roles
- SSE streaming dashboard with pipeline stepper and evidence panel
- Jira ticket intake + Git-agnostic PR creation (GitHub/GitLab/Bitbucket)
- Full Hallmark-compliant design system: OKLCH colors, type pairing, dark/light mode
- Budget tracking (visible, no hard cap), scope guard, secret scanning, HITL pause, audit trail

### Out of Scope
- CI/CD for the factory itself (Phase 3)
- Multi-provider AI (DeepSeek-only for MVP; adapter interface for future)
- Vision API (DeepSeek text-only; screenshots are human evidence)
- Community plugin system (Phase 4)
- Claude/Anthropic integration
- LangGraph or LangChain

## Capabilities

### New Capabilities
- `pipeline-orchestration`: State machine, role dispatch, artifact persistence, retry logic
- `intake-gate`: Ticket completeness scoring (0–100), G1 threshold validation, bounce feedback
- `architecture-role`: Read-only repo exploration, design doc generation, AC coverage mapping
- `implementation-role`: Code generation with scope guard, build/lint validation (G3)
- `testing-role`: Independent test generation from AC, Playwright screenshots, evidence capture
- `review-role`: Independent diff review against AC/security/conventions, severity-ordered findings
- `pr-creation`: Git-agnostic PR opening, secret scan, auto-generated body with evidence links
- `dashboard-ui`: Pipeline stepper, SSE streaming per role, evidence panel, PR summary, dark/light mode
- `guardrails`: Budget accumulation, path-based scope guard, HITL pause, event audit trail
- `jira-integration`: Jira ticket intake via Jira REST API
- `git-provider-abstraction`: GitHub/GitLab/Bitbucket adapter with unified PR creation interface

### Modified Capabilities
None (greenfield project; `openspec/specs/` is empty).

## Approach

**Backend**: Python FastAPI async server. Custom orchestrator wrapping the OpenAI SDK (DeepSeek-compatible). `transitions` library for the state machine — guards validate gates programmatically (not via LLM). Each role gets a fresh messages array (no shared context for Tester/Reviewer). DeepSeek streams SSE chunks; FastAPI relays via `StreamingResponse`. SQLite for MVP, PostgreSQL for multi-user scale.

**Frontend**: React 19 + Vite + Tailwind CSS v4. EventSource API for SSE. @tanstack/react-query for state. Pencil MCP generates components from Hallmark-compliant designs.

**Design**: Hallmark anti-patterns and foundations extracted as `design-system.md` spec → Pencil MCP `.pen` file → React components. OKLCH palette, paired display/body type, asymmetric layout, ×4 spacing scale.

**Git**: GitPython for local ops. Abstract `GitProvider` interface with GitHub/GitLab/Bitbucket implementations. `gh` CLI for GitHub provider in MVP.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/` | New | FastAPI server, orchestrator, state machine, DeepSeek client, Jira client |
| `frontend/` | New | React + Vite SPA, SSE dashboard, pipeline stepper, evidence panel |
| `design/` | New | `design-system.md` spec, Pencil `.pen` files, exported assets |
| `config/` | New | `.agentfactory/config.yaml` — role definitions, tool permissions, pipeline settings |
| `db/` | New | SQLAlchemy models, Alembic migrations, seed data |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| DeepSeek JSON not schema-conformant | Medium | Pydantic validation + retry with error feedback; fallback to regex extraction |
| Scope guard imperfect enforcement | Medium | Path-based whitelist; log-and-warn for edits outside `components[]` (advisory, not denial) |
| Orchestration complexity grows during build | Medium | 2-role MVP first (Phase 0), add roles incrementally |
| DeepSeek API downtime | Low | Mock mode (`AGENT_FACTORY_MOCK=1`) for dev; provider adapter for future fallback |
| No vision API limits Reviewer | Low | Reviewer processes text diffs only; screenshots are human-facing evidence |
| Hallmark-to-DeepSeek fidelity gap | Low | Hallmark is a spec, not runtime; Pencil MCP enforces visual constraints |

## Rollback Plan

This is greenfield. No existing system to roll back to. Rollback = stop development and delete the repo. For incremental rollback: each phase produces a working artifact. If a phase fails, revert to the previous phase's state via git.

## Dependencies

- DeepSeek API key (platform.deepseek.com)
- Jira API key + instance URL (team's Jira Cloud/Server)
- Pencil MCP initialized and `.pen` file created
- OpenSSL for local dev (no purchased domain needed for MVP)
- Git installed on server; `gh` CLI for GitHub provider

## Success Criteria

- [ ] Intake gate scores a ticket ≥ 80 and bounces one < 80 with missing fields listed
- [ ] All 6 gates fail hard — broken build, missing tests, or CHANGES_REQUIRED blocks progress
- [ ] Tester and Reviewer run fresh sessions (no Developer context) and produce independent verdicts
- [ ] A complete run opens a real PR against a target repo with auto-generated body and evidence links
- [ ] Dashboard shows pipeline stepper, per-role streaming output, and evidence panel in real time
- [ ] Scope guard logs warnings when edits fall outside declared `components[]`
- [ ] Budget tracker accumulates per-run cost with model-aware pricing

## Phases

| Phase | Duration | Deliverables |
|-------|----------|-------------|
| **0 — Foundation** | 1–2 weeks | FastAPI + React scaffold, state machine, 2 roles (Intake + Developer), 2 gates (G1 + G3), SSE streaming, SQLite persistence, minimal dashboard |
| **1 — Complete Pipeline** | 2–3 weeks | All 6 roles + 6 gates, independent sessions, evidence capture (screenshots + API responses), retry loops, PR creation |
| **2 — Frontend Polish** | 1–2 weeks | Pencil MCP dashboard designs, Hallmark anti-pattern audit, dark/light mode, evidence panel, PR summary |
| **3 — Hardening** | 1–2 weeks | Budget tracking + display, scope guard, secret scanning, HITL pause, audit trail, CLI, PostgreSQL migration |
| **4 — Community** | Ongoing | Multi-provider adapter, Docker Compose, CI/CD, plugin system, documentation site |

## Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| 1 | Scope guard: advisory (warn + log) or absolute (deny)? | Confirmed | Advisory — confirmed by user |
| 2 | Jira integration depth: ticket intake only, or status sync back to Jira? | Pending | Intake confirmed; write-back TBD in design |
| 3 | Target repo per run: one configurable repo or any repo the user has access to? | Pending | Design phase — likely one repo per project config |
| 4 | Auth strategy: OAuth2 (Google/GitHub SSO) or email/password? | Pending | Design phase; multi-user requires auth |
| 5 | Streaming granularity: per-role output or per-chunk relay? | Pending | Per-role tagged chunks for dashboard routing |

## Next Steps

1. **sdd-spec**: Write delta specs for each capability listed above
2. **sdd-design**: Sequence diagrams, data model, API contracts, auth flow
