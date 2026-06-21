# Exploration: Agent Factory — Open Source Version

**Date**: 2026-06-21
**Status**: Complete — ready for proposal
**Greenfield**: Yes (empty working directory)

---

## Executive Summary

Agent Factory can be built open-source using DeepSeek API as the AI engine, Python (FastAPI) backend, a custom Python state machine with the `transitions` library for pipeline orchestration, and a React/Next.js frontend with SSE streaming. The DeepSeek API is fully OpenAI-compatible and supports all required patterns (streaming, tool calling, JSON output, usage tracking). The orchestration layer (Agent SDK replacement) is the largest build effort — roughly 60% of the backend work. Hallmark's design principles are extractable as a design system specification for Pencil MCP to render visually.

---

## 1. Feasibility Analysis

### 1.1 Claude Agent SDK → DeepSeek API Mapping

| Agent SDK Capability | DeepSeek Equivalent | Verdict |
|---|---|---|
| `query()` — single-turn chat | `client.chat.completions.create()` via OpenAI SDK | ✅ Direct match |
| `AgentDefinition` — system prompt + tools + output format per role | Python `dataclass` / Pydantic model wrapping system prompt, tools array, response_format | ✅ Must build thin wrapper |
| `output_format` (JSON Schema) | `response_format: {"type": "json_object"}` + prompt-embedded schema | ✅ Supported (note: no strict JSON Schema enforcement — must validate post-hoc) |
| `can_use_tool` — tool permission scoping per role | Custom tool dispatch layer that filters available tools by role | ✅ Must build — the orchestrator owns tool dispatch |
| `hooks` — lifecycle callbacks | `transitions` library callbacks (`before`, `after`, `on_enter`, `on_exit`) | ✅ Better fit — dedicated state machine library |
| `permission_mode` — read-only vs. write | Role-level tool whitelist in orchestrator config | ✅ Must build |
| `setting_sources` — `.claude/` reuse | Config YAML / `.env` per project, or `.agentfactory/` directory | ✅ Must build |
| `total_cost_usd` — budget tracking | DeepSeek returns `usage.total_tokens`. Cost = tokens × model price. | ✅ Computable (no built-in USD field — must calculate) |
| Streaming output | `stream=True` returns SSE-compatible chunks | ✅ Supported |
| Independent sub-agents (fresh sessions) | New API call with fresh messages array — no shared context unless explicitly passed | ✅ Stateless by default — fresh session = new messages array |
| Thinking/reasoning mode | `reasoning_effort="high"` + `extra_body={"thinking": {"type": "enabled"}}` | ✅ Supported (DeepSeek's key differentiator) |

**Bottom line**: DeepSeek API covers all the LLM-level needs. The orchestration layer (Agent SDK replacement) is the build work — roughly 1,500–2,500 lines of Python.

### 1.2 State Machine

The original spec says: **NO LangGraph, custom Python state machine**.

**Recommendation: `transitions` library (pytransitions)**

```python
# Conceptual pipeline model
from transitions import Machine

class PipelineRun:
    states = ['intake', 'gate1', 'architecture', 'gate2',
              'implementation', 'gate3', 'testing', 'gate4',
              'review', 'gate5', 'gate6', 'pr', 'done', 'bounced', 'failed']

    transitions = [
        # Happy path
        {'trigger': 'intake_complete', 'source': 'intake', 'dest': 'gate1'},
        {'trigger': 'pass_g1', 'source': 'gate1', 'dest': 'architecture',
         'conditions': 'score_ge_80'},
        {'trigger': 'arch_complete', 'source': 'architecture', 'dest': 'gate2'},
        {'trigger': 'pass_g2', 'source': 'gate2', 'dest': 'implementation',
         'conditions': 'files_exist_and_ac_covered'},
        # ... etc.

        # Failure paths (FAIL HARD)
        {'trigger': 'fail_g1', 'source': 'gate1', 'dest': 'bounced'},
        {'trigger': 'retry_arch', 'source': 'gate2', 'dest': 'architecture'},
        # Loop paths (max 2 retries)
        {'trigger': 'loop_impl', 'source': ['gate3', 'gate4', 'gate5'],
         'dest': 'implementation', 'unless': 'max_loop_exceeded'},
    ]

    def __init__(self):
        self.machine = Machine(model=self, states=...,
                               transitions=..., initial='intake')
```

**Why `transitions`**:
- Lightweight (pure Python, no deps)
- Guards/conditions: perfect for gate validation (`score ≥ 80`, `files exist`, `build passes`)
- Callbacks: `on_enter_gate1` triggers validation, `on_exit_architecture` saves artifacts
- Hierarchical: can nest `implementation` with sub-states for retry counting
- Async support: `AsyncMachine` for non-blocking pipeline execution
- Mature: 5.6k stars, actively maintained
- Graphviz export: auto-generate state diagrams for debugging

**Alternative considered**: `python-statemachine` — more feature-rich but heavier. `transitions` is simpler and maps directly to the pipeline phases.

### 1.3 Streaming

DeepSeek API supports standard SSE streaming via `stream=True`:

```
POST /chat/completions  →  SSE chunks (data: {...}\n\n)
```

Each chunk contains `choices[0].delta.content` (and optionally `reasoning_content` for thinking mode).

**Architecture**:
```
Orchestrator → DeepSeek API (stream=True)
                  ↓ SSE chunks
            SSE Relay (FastAPI StreamingResponse)
                  ↓
            Frontend (EventSource / fetch + ReadableStream)
```

FastAPI's `StreamingResponse` can relay DeepSeek chunks directly to the browser with minimal transformation. Each role's output is tagged with `role` and `stage` for the FE to route to the correct panel.

### 1.4 Tool Calling / Function Calling

DeepSeek supports standard OpenAI-format tool calling:

```python
tools = [{
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "List files in a directory",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"}
            },
            "required": ["path"]
        }
    }
}]

response = client.chat.completions.create(
    model="deepseek-v4-pro",
    messages=messages,
    tools=tools  # Only tools this role is allowed to use
)
```

**Gate validation** uses programmatic checks (not LLM tool calls):
- `os.path.exists()` for G2 file checks
- `score >= 80` for G1 completeness
- `git diff --stat` for G3 scope guard
- Subprocess calls for build/lint/test

The orchestrator runs these validations directly — no LLM needed at gates.

### 1.5 Independent Sessions

The Tester and Reviewer get FRESH sessions — no message history from previous roles.

**Implementation**: Each role gets a fresh `messages = [{"role": "system", "content": role_system_prompt}]` array. The orchestrator injects only the artifacts needed (e.g., design.md for Tester, diff for Reviewer). No shared conversation context.

DeepSeek's API is stateless — each call is independent. This is natural behavior, not a constraint.

---

## 2. Stack Recommendations

### 2.1 Frontend: React + Vite + Tailwind CSS

| Option | Verdict | Reason |
|---|---|---|
| **React + Vite** | ✅ Recommended | Largest ecosystem, Pencil MCP has React codegen, SSE via EventSource is trivial |
| Next.js | ⚠️ Overkill | SSR not needed for a dashboard SPA; adds complexity |
| Svelte | ❌ | Pencil MCP codegen targets React primarily; smaller ecosystem |
| HTMX + FastAPI | ⚠️ Possible | Simpler but less capable for streaming dashboard |

**Frontend stack**:
- **React 19** (Vite) — fast dev, small bundle
- **Tailwind CSS v4** — utility-first, Pencil MCP generates Tailwind
- **@tanstack/react-query** — server state, caching
- **EventSource API** — native SSE consumption
- **React Router** — simple SPA routing

### 2.2 Backend: Python + FastAPI

| Option | Verdict | Reason |
|---|---|---|
| **Python + FastAPI** | ✅ Recommended | Matches original, async-first, SSE native, OpenAPI docs auto-generated |
| Node.js + Express | ⚠️ | Less natural for AI orchestration; Python dominates ML/AI tooling |
| Go | ❌ | Overengineered for this; Python's AI ecosystem is unmatched |

**Backend stack**:
- **FastAPI** — async endpoints, `StreamingResponse` for SSE, automatic OpenAPI docs
- **SQLAlchemy 2.0** (async) + **Alembic** — ORM + migrations
- **Pydantic v2** — request/response validation, role config schemas
- **httpx** — async HTTP for DeepSeek API calls (or OpenAI SDK directly)
- **gitpython** — programmatic git operations
- **transitions** — state machine

### 2.3 Database: SQLite (MVP) → PostgreSQL (scale)

| Option | Verdict | Reason |
|---|---|---|
| **SQLite** | ✅ MVP | Zero setup, single file, perfect for single-user/desktop |
| **PostgreSQL** | ✅ Scale | Multi-user, concurrent writes, JSONB for artifacts |

SQLite for the initial build. Migrate to PostgreSQL only when:
- Multiple concurrent users/runs
- Need for real-time notifications (LISTEN/NOTIFY)
- Community deployment

**Schema sketch**:
```sql
runs (id, repo_path, ticket_raw, status, started_at, completed_at)
stages (id, run_id, role, state, started_at, completed_at, retry_count)
artifacts (id, stage_id, type, content_json, created_at)
events (id, run_id, stage_id, event_type, payload_json, timestamp)
evidence (id, stage_id, type, file_path, metadata_json)
gates (id, run_id, gate_name, passed, score, failure_reason, timestamp)
```

### 2.4 Real-time: SSE (not WebSockets)

| Option | Verdict | Reason |
|---|---|---|
| **SSE (Server-Sent Events)** | ✅ Recommended | Unidirectional (server→FE), built into browsers, simpler than WS, auto-reconnect |
| WebSockets | ⚠️ | Bidirectional overkill; FE doesn't send streaming data |
| Polling | ❌ | Wasteful, not real-time |

SSE is the right fit: the FE only consumes streamed output, never sends mid-stream. FastAPI's `StreamingResponse` with `text/event-stream` content type is the canonical approach.

### 2.5 Git Integration: GitPython + gh CLI

| Option | Verdict | Reason |
|---|---|---|
| **GitPython** | ✅ | Programmatic git operations (diff, status, branch, commit) |
| **GitHub CLI (gh)** | ✅ | PR creation (`gh pr create`), checks status |
| Subprocess git | ⚠️ | Works but less ergonomic than GitPython |

**Approach**: GitPython for all local git operations, `gh` CLI for GitHub API operations (PR creation, status checks). The PR role calls `gh pr create` as a subprocess. For a Git-agnostic version, abstract behind a `GitProvider` interface.

### 2.6 Testing the Factory Itself

| Layer | Tool | Purpose |
|---|---|---|
| Unit | **pytest** + **pytest-asyncio** | State machine transitions, gate validation, role config |
| Integration | **pytest** + **httpx** (TestClient) | API endpoints, SSE streaming, artifact persistence |
| E2E | **Playwright** | Full pipeline runs, screenshot capture, FE verification |
| Mock LLM | Custom mock returning fixtures | Fast tests without API calls (AGENT_FACTORY_MOCK=1 pattern) |

---

## 3. Hallmark + Pencil Integration Strategy

### 3.1 Hallmark is Claude-Specific — Principles Are Portable

Hallmark is a Claude Code skill (wraps the LLM with design constraints). It cannot be directly used with DeepSeek. However, its **design principles and anti-pattern rules are fully extractable** as a specification.

### 3.2 Design Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│ HALLMARK PRINCIPLES (design system spec)                        │
│ • Anti-patterns: no purple gradients, no icon-tile cards, etc.  │
│ • Foundations: OKLCH colors, type pairing, named space scale    │
│ • Macrostructure: pick before dressing (Hero, Split, Editorial)  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ feeds into
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ PENCIL MCP (visual design tool)                                 │
│ • Design-kit-first: component library, variables, themes         │
│ • Precise layout: frames, grids, spacing                         │
│ • Export: PNG/JPEG for evidence screenshots                      │
│ • Codegen: Tailwind CSS + React components                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ generates
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ IMPLEMENTATION (React + Tailwind)                               │
│ • Components from Pencil designs                                │
│ • Tailwind config from Pencil variables (colors, spacing)        │
│ • Anti-pattern audit during review phase                        │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Mapping Hallmark → Pencil

| Hallmark Principle | Pencil MCP Implementation |
|---|---|
| OKLCH color palette | Pencil variables with `type: "color"`, OKLCH values |
| Type pairing (display + body) | Pencil text styles with font variables |
| Named space scale (×4) | Pencil number variables (spacing-unit: 16) |
| Anti-pattern avoidance | Manual review checklist; potentially an audit step |
| Macrostructure selection | Pencil frame layouts matching Hallmark archetypes |
| Exponential ease-out motion | Tailwind config animation settings |

### 3.4 Practical Approach

1. **Extract Hallmark's design foundations** into a `design-system.md` spec file — this becomes the design constitution
2. **Use Pencil MCP** to create the `.pen` design file with:
   - Dashboard layout (stepper, panels, streaming output)
   - Component library (status badges, evidence cards, pipeline stepper)
   - Light/dark themes via Pencil variables
3. **Audit** the Pencil design against Hallmark's anti-pattern rules before implementation
4. **Generate code** from Pencil designs, not from Hallmark

---

## 4. DeepSeek API Deep-Dive

### 4.1 Models Available

| Model | Context | Max Output | Cost (Input/Output per 1M tokens) | Use Case |
|---|---|---|---|---|
| **deepseek-v4-pro** | 1M | 384K | $1.74 / $3.48 | Architect, Reviewer (needs deep reasoning) |
| **deepseek-v4-flash** | 1M | 384K | $0.14 / $0.28 | Intake, Developer (needs speed + low cost) |

Both support:
- Streaming (`stream=True`)
- Tool calling (standard OpenAI format)
- JSON output (`response_format: { "type": "json_object" }`)
- System prompts
- Thinking/reasoning mode (`reasoning_effort="high"`)
- Context caching (reduces cost for repeated system prompts)

### 4.2 Cost Tracking

DeepSeek returns token counts per response:
```json
"usage": {
  "prompt_tokens": 10,
  "completion_tokens": 30,
  "total_tokens": 40,
  "prompt_cache_hit_tokens": 0,
  "prompt_cache_miss_tokens": 0,
  "completion_tokens_details": { "reasoning_tokens": 0 }
}
```

**Cost formula**: `(prompt_tokens × input_price + completion_tokens × output_price) / 1,000,000`

No built-in USD cost field — the orchestrator must compute it. Accumulate per run for budget tracking. Context caching via repeated system prompts can reduce input cost by ~90% (cache hit at $0.145/1M vs $1.74/1M for v4-pro).

### 4.3 Streaming Deep-Dive

DeepSeek streams SSE chunks with this structure:
```
data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}],...}
data: {"choices":[{"delta":{"content":" world"},"finish_reason":null}],...}
data: {"choices":[{"delta":{"content":""},"finish_reason":"stop"}],...}
data: [DONE]
```

Thinking mode adds `delta.reasoning_content` — can be surfaced separately in the FE as "reasoning trace."

### 4.4 Mock Mode

Same pattern as the original: `AGENT_FACTORY_MOCK=1` in environment. The orchestrator returns pre-defined fixture responses instead of calling the API. Essential for:
- Fast development iteration
- Testing gate logic without API costs
- CI/CD pipeline runs
- Demo mode

### 4.5 Rate Limits & Concurrency

| Model | Concurrency Limit |
|---|---|
| deepseek-v4-pro | 500 requests |
| deepseek-v4-flash | 2500 requests |

No enforced TPM/RPM limits — can handle up to 1T tokens/day. Concurrency is the only throttle. For an MVP, this is effectively unlimited.

---

## 5. Gap Analysis — Original vs. Open-Source

| Capability | Original (Claude + Agent SDK) | Open-Source (DeepSeek) | Gap Size |
|---|---|---|---|
| **Agent orchestration** | Agent SDK `query()` | Custom orchestrator wrapping OpenAI SDK | 🔴 Large — must build |
| **Output format (JSON Schema)** | `output_format` with strict schema enforcement | `response_format: json_object` (loose) + post-hoc Pydantic validation | 🟡 Medium — must add validation layer |
| **Tool permission scoping** | `can_use_tool` declarative | Custom tool whitelist per role in orchestrator config | 🟡 Medium — straightforward to implement |
| **Budget tracking** | `total_cost_usd` built-in | Compute from token counts × model price | 🟢 Small — simple arithmetic |
| **Setting sources** | `.claude/` auto-reuse | Custom `.agentfactory/` config directory | 🟡 Medium — must design config format |
| **Streaming** | Built-in in Agent SDK | `stream=True` in OpenAI SDK | 🟢 Small — works identically |
| **Independent sub-agents** | Fresh `query()` per role | Fresh messages array per role | 🟢 Small — stateless by nature |
| **System prompts per role** | `AgentDefinition.system_prompt` | `messages[0] = {"role": "system", "content": ...}` | 🟢 Small — standard pattern |
| **Hooks (lifecycle)** | `hooks` in AgentDefinition | `transitions` callbacks (on_enter, before, after) | 🟢 Small — state machine handles this |
| **Reasoning/thinking** | Not originally used | `reasoning_effort="high"` — DeepSeek's killer feature | 🟢 Bonus — enhances Architect + Reviewer |
| **Context caching** | Not originally used | DeepSeek context cache (90% cost reduction on repeated prompts) | 🟢 Bonus — reduces cost for repeated runs |
| **Image/vision** | Claude supports images | DeepSeek V4 is text-only (no vision API yet) | 🔴 Gap — affects screenshot-based roles |
| **E2E testing screenshots** | Playwright (browser) | Playwright (same) | 🟢 No gap — Playwright is language-agnostic |

### Key Gaps

1. **🔴 Orchestration Layer**: The largest build effort. Must reimplement Agent SDK patterns: role definitions, tool dispatch, artifact management, event emission, retry logic. Estimated 1,500–2,500 lines of Python.

2. **🟡 JSON Schema Validation**: DeepSeek's `json_object` mode only guarantees valid JSON, not schema-conformant JSON. Must add Pydantic validation layer that retries on parse failure.

3. **🔴 No Vision API**: DeepSeek V4 does not support image inputs. The Reviewer role cannot "look at" screenshots. Mitigation: screenshots are for human evidence only; the Reviewer processes text diffs and test results.

4. **🟡 Config System**: Must design `.agentfactory/config.yaml` format for role definitions, tool permissions, pipeline settings.

---

## 6. Phased Build Plan

### Phase 0: Foundation (MVP vertical slice)
```
Duration: 1-2 weeks
Goal: Single-ticket pipeline that proves the concept
```

**What to build**:
1. **Project scaffold**: FastAPI backend + React/Vite frontend + SQLite
2. **State machine**: `transitions` library modeling all phases and gates
3. **Orchestrator core**: Role dispatch, DeepSeek API wrapper, mock mode
4. **Two roles**: Intake (score ticket) + Developer (generate a file)
5. **Two gates**: G1 (score ≥ 80) + G3 (build passes)
6. **SSE streaming**: Backend → Frontend real-time output
7. **Minimal dashboard**: Pipeline stepper + streaming output panel

**Smallest vertical slice**: Submit a ticket → Intake scores it ≥ 80 → Developer implements → Build passes → Done.

### Phase 1: Complete Pipeline
```
Duration: 2-3 weeks
Goal: All 6 roles + 6 gates working end-to-end
```

**What to build**:
1. Remaining roles: Architect, Tester, Reviewer, PR
2. Remaining gates: G2, G4, G5, G6
3. Independent sessions for Tester + Reviewer
4. Artifact persistence (design.md, test results, screenshots)
5. Retry/loop logic (max 2 per stage)
6. Evidence panel: screenshots, test output, PR link

### Phase 2: Frontend Polish
```
Duration: 1-2 weeks
Goal: Production-quality dashboard
```

**What to build**:
1. Pencil MCP design for complete dashboard
2. Apply Hallmark principles (anti-pattern audit)
3. Streaming output with syntax highlighting
4. Evidence panel with screenshots, API responses
5. PR summary panel
6. Dark mode

### Phase 3: Hardening
```
Duration: 1-2 weeks
Goal: Production-ready
```

**What to build**:
1. Budget tracking + enforcement
2. Scope guard (deny edits outside declared components)
3. Secret scanning (gitleaks or detect-secrets)
4. HITL pause at PR_READY
5. Audit trail (events table)
6. CLI tool (`agentfactory run --ticket=...`)
7. Configuration file format (.agentfactory/)

### Phase 4: Community
```
Duration: Ongoing
Goal: Open-source adoption
```

**What to build**:
1. GitHub Actions CI for the factory itself
2. Plugin system for custom roles/gates
3. Multi-provider support (OpenAI, Anthropic as alternates)
4. Docker Compose for one-command setup
5. Documentation site

### Key Risks

| Risk | Severity | Mitigation |
|---|---|---|
| DeepSeek JSON output not schema-conformant | Medium | Pydantic validation + retry with error feedback |
| DeepSeek API instability/downtime | Medium | Mock mode fallback; multi-provider in Phase 4 |
| Orchestration complexity explodes | Medium | Start with 2-role MVP; add roles incrementally |
| Scope guard is hard to enforce perfectly | High | Path-based whitelist; accept best-effort for MVP |
| No vision API limits Reviewer capabilities | Low | Reviewer only processes text; screenshots are human evidence |
| Rate limits at scale | Low | 500 concurrent requests is far beyond MVP needs |

---

## 7. Key Questions for the User

These need answers before proceeding to the proposal phase:

### Architecture
1. **Single-user or multi-user?** Is this a personal tool (desktop, single SQLite) or a team server (multi-user, PostgreSQL, auth)?
2. **Runtime target**: Browser-based SPA? Desktop (Electron/Tauri)? Self-hosted server with web UI? CLI-first with optional web UI?
3. **Scope guard strictness**: Absolute enforcement (deny any edit outside declared files) or advisory (warn but allow)? Absolute enforcement is complex and may break legitimate refactors.

### AI Engine
4. **Multi-provider from day one?** Or DeepSeek-only for MVP, with provider abstraction added later?
5. **Thinking mode**: Enable for all roles or only Architect + Reviewer? It increases token usage ~3× but improves quality.
6. **Budget**: What's the max cost per pipeline run you're comfortable with? (Estimate: $0.50–$2.00 per full run with v4-pro for heavy roles)

### Design
7. **Pencil MCP first or Hallmark principles first?** Do you want to start with a Pencil-designed UI (visual precision) or extract Hallmark principles into a design spec first (constitution before implementation)?
8. **Design system scope**: Full design system with component library, or just the dashboard layout?

### DevOps
9. **GitHub-only or Git-agnostic?** Should PR creation support GitLab/Bitbucket, or is GitHub + `gh` CLI sufficient?
10. **CI/CD for the factory**: Should the factory itself have CI? (Tests, linting, type checking for the orchestrator code)

### Target Audience
11. **Who is this for?** Personal productivity tool? Internal team tool? Open-source community project? This affects UX polish, documentation depth, and plugin extensibility.

---

## Affected Areas

Greenfield project — no existing code to affect. All areas are new:

| Area | Description |
|---|---|
| `backend/` | FastAPI server, orchestrator, state machine, DeepSeek client |
| `frontend/` | React + Vite dashboard, SSE consumer, pipeline stepper |
| `design/` | Pencil `.pen` files, Hallmark design spec, exported assets |
| `config/` | `.agentfactory/` directory format, role definitions, tool permissions |
| `docs/` | Architecture decision records, API docs, user guide |

---

## Recommendation

**Proceed to proposal phase with Python + FastAPI + React + DeepSeek stack.**

The feasibility is HIGH. All required capabilities exist in the DeepSeek API. The orchestration layer is the only significant build effort, and the `transitions` library provides a solid foundation for it. The MVP (Phase 0) can be built in 1–2 weeks and will prove the concept.

**Critical path**: Orchestrator + state machine + 2 roles + SSE streaming. Everything else builds on this.

**Before proposal**: Answer the key questions above — especially single-user vs. multi-user, runtime target, and provider strategy. These decisions shape the entire architecture.

---

## Skill Resolution

`paths-injected` — orchestrator injected `sdd-explore` skill path directly. No additional skills loaded (greenfield — no codebase-specific skills needed).
