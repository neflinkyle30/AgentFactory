# Delta Spec: Agent Factory OSS

## Summary

Agent Factory automates the ticket-to-PR pipeline via an 8-phase state machine with 8 hard gates. A Jira ticket enters, independent AI roles process it through Intake → Spec → Design → Tasks → Develop → Verify → Review → PR, and a real PR opens against the target repo. No human writes boilerplate.

---

## Capability: `pipeline-orchestration`

State machine that executes the 8-phase pipeline, enforces hard gates, manages retries, and persists run artifacts. The orchestrator is the backbone — every other capability plugs into it.

### Requirements

- **ORCH-REQ-1**: The system SHALL implement an 8-phase state machine with the following linear traversal: `INTAKE → SPEC → DESIGN → TASKS → DEVELOP → VERIFY → REVIEW → PR`, where each transition is guarded by a programmatic gate that must pass before the next phase can start.
- **ORCH-REQ-2**: The system SHALL persist the current state, gate results, artifacts, and events per run in a database, surviving process restarts and enabling resumption.
- **ORCH-REQ-3**: The system SHALL support bounded retry loops: Spec/Design may retry once, Develop↔Verify may loop up to 2 times, Develop↔Review may loop up to 2 times. Any phase may transition to FAILED on budget/time/iteration exhaustion.
- **ORCH-REQ-4**: The system SHALL dispatch each role execution as a fresh session (independent messages array, no shared context carryover), with Verify and Review receiving NO developer reasoning — only ticket, specs, and repo state.
- **ORCH-REQ-5**: The system SHALL emit SSE events at every phase transition, gate evaluation, and role output chunk, keyed by `run_id`, to enable real-time dashboard streaming.
- **ORCH-REQ-6**: The system SHALL enforce gate evaluations programmatically (not via LLM judgment) — G1 uses score≥80, G2 checks file existence, G3 checks build/lint exit codes, G4 counts test-per-AC, G5 checks verdict enum, G6 checks green status.
- **ORCH-REQ-7**: The system SHALL support configurable HITL (Human-In-The-Loop) pause at `PR_READY`, awaiting manual approval via API before proceeding to PR creation.
- **ORCH-REQ-8**: The system SHALL record an immutable audit trail of events (phase_start, phase_end, gate_eval, retry, error, budget_exceeded) with sequence numbers per run.

### Scenarios

#### Happy path: full pipeline execution

- **Given** a Jira ticket has been submitted and passed Intake (G1)
- **When** the orchestrator starts the run
- **Then** it transitions through SPEC → DESIGN → TASKS → DEVELOP → VERIFY → REVIEW → PR, evaluating each gate programmatically, and reaches the DONE state with a PR opened.

#### Gate failure: G3 build fails

- **Given** the Developer has produced code changes
- **When** G3 evaluates `build` or `lint` and finds a non-zero exit code
- **Then** the orchestrator transitions the run to DEVELOP_RETRY with a retry counter, invokes the Developer agent again with the build error, and re-evaluates G3.

#### Gate failure: retry budget exhausted

- **Given** the Developer has failed G3 twice (max retries for DEVLOP→DEVLOP_RETRY)
- **When** the orchestrator evaluates the retry counter and finds it equals the max
- **Then** the run transitions to FAILED, an event is logged, and the dashboard shows the failure reason.

#### Budget exhaustion mid-run

- **Given** a run is in the DEVELOP phase and the accumulated token cost exceeds the configured budget
- **When** the orchestrator checks budget after role completion
- **Then** the run transitions to FAILED and emits a budget_exceeded event with accumulated cost.

#### HITL pause at PR_READY

- **Given** all gates G1–G7 are green and HITL is enabled
- **When** the orchestrator reaches the PR_READY state
- **Then** the run pauses and emits an awaiting_approval event. The run SHALL NOT proceed to PR until the `/approve` endpoint is called.

---

## Capability: `intake-agent`

Validates incoming Jira tickets against a completeness rubric, normalizes fields, scores 0–100, and bounces tickets below the G1 threshold back to the user with actionable feedback.

### Requirements

- **INTAKE-REQ-1**: The system SHALL validate every ticket against a required template including: title, description, acceptance criteria in Given-When-Then format, priority, and target component(s).
- **INTAKE-REQ-2**: The system SHALL compute a deterministic completeness score (0–100) using a rubric-based evaluation, not an LLM impression. The rubric SHALL weight: AC presence and quality (40pts), description clarity (25pts), title specificity (15pts), priority/sizing (10pts), component identification (10pts).
- **INTAKE-REQ-3**: The system SHALL normalize the ticket into a canonical JSON structure with fields: `normalized_title`, `normalized_description`, `acceptance_criteria[]` (each with `given`, `when`, `then`), `priority`, `components[]`, `raw_ticket` (original form data).
- **INTAKE-REQ-4**: The system SHALL bounce tickets scoring < 80, producing a BOUNCED response containing: `completeness_score`, `missing[]` (list of missing/insufficient fields), `suggestions[]` (actionable improvements), and the `normalized_ticket` partial for user review.
- **INTAKE-REQ-5**: The system SHALL pass tickets scoring ≥ 80 to the SPEC phase, attaching the full `normalized_ticket` as the run artifact.
- **INTAKE-REQ-6**: The system SHALL support Jira ticket intake via two modes: (a) Jira REST API — fetch ticket by key, parse fields from Jira's JSON, (b) Simulated form — a web form/template generates the ticket payload (MVP fallback).
- **INTAKE-REQ-7**: The system SHALL NOT access any git repository or filesystem during intake validation.

### Scenarios

#### Ticket passes intake

- **Given** a well-written ticket with 3 ACs in Given-When-Then, a clear description, specific title, priority set, and components listed
- **When** the Intake agent evaluates the ticket
- **Then** `completeness_score ≥ 80`, G1 passes, the normalized ticket is produced, and the run proceeds to SPEC.

#### Ticket bounces: missing ACs

- **Given** a ticket with a description but no acceptance criteria
- **When** the Intake agent evaluates the ticket
- **Then** `completeness_score < 80`, the run transitions to BOUNCED, and the response includes `missing: ["acceptance_criteria"]` and `suggestions: ["Write at least 1 AC in Given-When-Then format"]`.

#### Ticket bounces: vague ACs

- **Given** a ticket with one AC written as "It should work"
- **When** the Intake agent evaluates the ticket
- **Then** `completeness_score < 80` because AC quality score is low, and `suggestions[]` includes guidance on writing specific Given-When-Then ACs.

#### Jira API mode intake

- **Given** the factory is configured with a valid Jira API key and instance URL
- **When** a user submits run with `ticket_source: "jira"` and `ticket_key: "PROJ-123"`
- **Then** the Intake agent fetches the ticket from Jira REST API, parses fields, and normalizes into the canonical structure before scoring.

---

## Capability: `spec-agent`

Writes formal requirements in Given-When-Then format from the normalized intake ticket. Every acceptance criteria from the ticket SHALL be covered by at least one spec scenario.

### Requirements

- **SPEC-REQ-1**: The system SHALL produce a formal specification document (`spec.md`) containing, for each acceptance criterion in the normalized ticket: a requirement statement using SHALL, and at least one scenario in Given-When-Then format.
- **SPEC-REQ-2**: The system SHALL validate that every acceptance criterion from the intake ticket is mapped to at least one requirement in the spec (coverage check).
- **SPEC-REQ-3**: The system SHALL identify and document edge cases and failure paths (timeout, invalid input, missing data) as additional scenarios, not just the happy path.
- **SPEC-REQ-4**: The system SHALL produce structured JSON output with: `requirements[]` (each with `id`, `statement`, `ac_id` reference), `scenarios[]` (each with `given`, `when`, `then`, `requirement_id` reference), `coverage_map` (mapping each AC to its requirements).
- **SPEC-REQ-5**: The system SHALL validate at G2 that the spec output contains all mandatory fields and passes the coverage check (no orphan ACs).
- **SPEC-REQ-6**: The system SHALL retry once if spec output fails JSON schema validation or coverage check; if the retry also fails, the run transitions to FAILED.
- **SPEC-REQ-7**: The system SHALL NOT access any git repository or filesystem during spec writing.

### Scenarios

#### Full coverage spec

- **Given** a normalized ticket with 3 ACs
- **When** the Spec agent generates the specification
- **Then** the output contains ≥3 requirements (one per AC, plus edge cases), each AC has ≥1 mapped scenario, the coverage map shows 100% AC coverage, and G2 passes.

#### Coverage gap detected

- **Given** a normalized ticket with 3 ACs, but the spec output covers only 2
- **When** G2 runs the coverage check
- **Then** G2 fails with `uncovered_acs: ["AC-3"]`, the spec agent retries once with the gap as feedback, and if the retry still fails, the run transitions to FAILED.

#### Edge case scenarios generated

- **Given** a normalized ticket describing a "user login" feature
- **When** the Spec agent generates the specification
- **Then** in addition to happy-path scenarios, the output includes scenarios for: invalid credentials, locked account, network timeout, empty fields, and rate limiting.

---

## Capability: `design-agent`

Explores the target repository (read-only), identifies real files affected by the change, and produces a technical design document with architecture decisions and file references that SHALL be programmatically validated to exist.

### Requirements

- **DESIGN-REQ-1**: The system SHALL explore the target repository using read-only tools (Glob, Grep, Read) to identify real files, directories, and conventions before producing any design output.
- **DESIGN-REQ-2**: The system SHALL produce a design document (`design.md`) containing: architecture decisions with rationale, affected component list, file-change plan, and task breakdown — all anchored to files discovered during exploration.
- **DESIGN-REQ-3**: The system SHALL output a structured `files_referenced[]` list of absolute paths that G2 validates programmatically with `os.path.exists()` before the gate passes. Any path that does not exist causes G2 to fail.
- **DESIGN-REQ-4**: The system SHALL produce a `components[]` list declaring which parts of the codebase will be modified, used by the scope guard during Develop.
- **DESIGN-REQ-5**: The system SHALL produce `tasks[]` — an atomic task breakdown where each task has a unique ID, a description, the files it affects, and the AC IDs it addresses.
- **DESIGN-REQ-6**: The system SHALL produce an `ac_coverage[]` map showing every acceptance criterion from the spec mapped to at least one task (100% coverage).
- **DESIGN-REQ-7**: The system SHALL mark inferred or unverified claims as `[ASSUMPTION]` in the design document, and these SHALL NOT block G2.
- **DESIGN-REQ-8**: The system SHALL retry once on G2 failure; if the retry also fails (files still don't exist or coverage still incomplete), the run transitions to FAILED.
- **DESIGN-REQ-9**: The system SHALL operate in read-only mode on the target repository — no writes, edits, or shell execution allowed.

### Scenarios

#### Design passes G2: all files exist

- **Given** a spec document and a target repo
- **When** the Design agent explores the repo, identifies 5 real files, and produces a design referencing those files
- **Then** G2 validates `os.path.exists()` for all 5 paths, all return true, every AC is covered, and G2 passes.

#### G2 fails: referenced file does not exist

- **Given** the Design agent produces a design referencing `/src/handlers/auth.go`
- **When** G2 runs `os.path.exists("/src/handlers/auth.go")` and returns `False`
- **Then** G2 fails with `missing_files: ["/src/handlers/auth.go"]`, and the design agent retries once with the missing paths as feedback.

#### Assumption handling

- **Given** the Design agent cannot determine the exact database migration strategy
- **When** it writes the design document
- **Then** the relevant section is marked `[ASSUMPTION]`, and G2 does NOT fail on that section — only on missing files and uncovered ACs.

#### AC coverage gap in design

- **Given** the spec has 5 ACs but the design's `ac_coverage[]` maps only 4
- **When** G2 evaluates coverage
- **Then** G2 fails with `uncovered_acs: ["AC-5"]`, and the design agent retries once.

---

## Capability: `tasks-agent`

Breaks the design into atomic implementation tasks, each mapped to specific files and acceptance criteria, producing a work plan the Developer agent can execute directly.

### Requirements

- **TASKS-REQ-1**: The system SHALL decompose the design document into atomic implementation tasks, where each task is a single, verifiable unit of work.
- **TASKS-REQ-2**: The system SHALL produce structured output: `tasks[]` where each task includes `id`, `description`, `files[]` (target files), `ac_ids[]` (acceptance criteria addressed), and `estimated_complexity` (small|medium|large).
- **TASKS-REQ-3**: The system SHALL ensure every spec requirement is mapped to at least one task (100% requirement-to-task coverage).
- **TASKS-REQ-4**: The system SHALL order tasks by dependency: foundational work (setup, scaffolding) before feature work, shared utilities before consumers, backend before frontend integration.
- **TASKS-REQ-5**: The system SHALL pass G4 only when: all spec requirements are mapped, task ordering is valid (no circular dependencies), and all task `files[]` entries reference paths declared in the design's `components[]`.
- **TASKS-REQ-6**: The system SHALL retry once on G4 failure; if the retry also fails, the run transitions to FAILED.
- **TASKS-REQ-7**: The system SHALL NOT access any git repository or filesystem for writing during task planning.

### Scenarios

#### Complete task breakdown

- **Given** a design with 8 spec requirements and a `components[]` list of 5 files
- **When** the Tasks agent decomposes the design
- **Then** output contains 5–12 atomic tasks, every requirement maps to ≥1 task, task ordering has no circular dependencies, and G4 passes.

#### Missing requirement coverage

- **Given** the spec has 8 requirements but the Tasks agent covers only 7
- **When** G4 evaluates requirement-to-task coverage
- **Then** G4 fails with `uncovered_requirements: ["REQ-8"]`, and the tasks agent retries once.

#### Circular dependency detection

- **Given** task T2 depends on T3, and T3 depends on T2
- **When** G4 validates task ordering
- **Then** G4 fails with `circular_dependency: ["T2 ↔ T3"]`, and the tasks agent retries once.

---

## Capability: `develop-agent`

Implements the task plan on a fresh git branch, respecting conventions and scope boundaries. Produces passing build and lint results. Advisory scope guard warns (but does not deny) on edits outside declared components.

### Requirements

- **DEVL-REQ-1**: The system SHALL clone the target repository into an isolated working directory per run (`runs/<run_id>/workdir`) and create a new branch named `agent-factory/<ticket-key>`.
- **DEVL-REQ-2**: The system SHALL implement each task from the task plan sequentially, applying edits to the files declared in each task's `files[]` list.
- **DEVL-REQ-3**: The system SHALL run `build` and `lint` commands after each task (or batch) and report results. The final G5 evaluation SHALL verify: `git diff` is non-empty, build exit code = 0, and lint exit code = 0.
- **DEVL-REQ-4**: The system SHALL enforce an advisory scope guard: if an edit touches a file outside the declared `components[]`, log a warning with `file`, `line`, and `component[]` context — but do NOT deny the edit.
- **DEVL-REQ-5**: The system SHALL produce a summary artifact including: files modified, build result, lint result, tests added/modified, and any scope deviations logged.
- **DEVL-REQ-6**: The system SHALL retry up to 2 times if G5 fails (build or lint not green). After 2 failures, the run transitions to FAILED.
- **DEVL-REQ-7**: The system SHALL track token usage and cost per Developer invocation, accumulating into the run's total budget.
- **DEVL-REQ-8**: The system SHALL NOT force-push, rebase, or self-merge. It SHALL only commit and push to the feature branch.

### Scenarios

#### Clean implementation passes G5

- **Given** a task plan with 5 tasks, a cloned repo, and a feature branch
- **When** the Developer implements all tasks, build passes, and lint passes
- **Then** `git diff` is non-empty, G5 passes, and the run proceeds to VERIFY.

#### Build failure triggers retry

- **Given** the Developer has implemented code that produces a build error
- **When** G5 evaluates build exit code and finds non-zero
- **Then** G5 fails, the Developer retries once with the build error output, and if the retry fixes it, G5 re-evaluates and passes.

#### Scope guard advisory warning

- **Given** the Developer edits `/src/unlisted/secret.ts` which is NOT in the design's `components[]`
- **When** the edit is applied
- **Then** the scope guard logs a warning: `scope_deviation: {file: "/src/unlisted/secret.ts", declared_components: [...]}`. The edit is NOT denied. The warning appears in the run's audit trail and dashboard.

#### Developer retries exhausted

- **Given** the Developer has failed G5 twice (build still broken after 2 retries)
- **When** the orchestrator evaluates the retry counter
- **Then** the run transitions to FAILED with the last build error preserved in the run artifact.

---

## Capability: `verify-agent`

Independently validates the implementation against the spec's acceptance criteria. Runs fresh (no developer session context), executes tests, captures evidence (screenshots, API responses), and produces a pass/fail verdict per AC.

### Requirements

- **VERF-REQ-1**: The system SHALL run the Verify agent in a fresh, independent session — receiving only the ticket, spec, and current repo state. It SHALL NOT receive the Developer's reasoning, prompts, or session history.
- **VERF-REQ-2**: The system SHALL execute at least one test per acceptance criterion from the spec. Tests may be existing (from the repo) or newly written by Verify.
- **VERF-REQ-3**: The system SHALL capture ≥1 screenshot as evidence using Playwright (MCP) of the running application or test results.
- **VERF-REQ-4**: The system SHALL capture API response payloads as evidence for backend changes, saving them as run artifacts.
- **VERF-REQ-5**: The system SHALL produce a verification report: `{tests[]: {ac_id, name, passed}, coverage_delta, screenshots[], evidence_paths[], verdict: PASSED|FAILED}`.
- **VERF-REQ-6**: The system SHALL pass G6 only when: all ACs have ≥1 passing test, the full test suite passes (no regressions), and ≥1 screenshot is captured.
- **VERF-REQ-7**: The system SHALL, on G6 failure, loop back to DEVELOP (not retry Verify itself). After 2 DEVLOP↔VERIFY loops, if G6 still fails, the run transitions to FAILED.
- **VERF-REQ-8**: The system SHALL persist all evidence artifacts (screenshots, API responses, test outputs) in `runs/<run_id>/evidence/` for dashboard display and PR body inclusion.

### Scenarios

#### All ACs verified

- **Given** a Developer implementation with 3 ACs, passing tests for each, a Playwright screenshot captured, and full suite green
- **When** the Verify agent runs independent validation
- **Then** the report shows all 3 tests passing, `verdict: PASSED`, ≥1 screenshot saved, and G6 passes.

#### Missing test for an AC

- **Given** the spec has 3 ACs but only 2 have corresponding tests
- **When** G6 evaluates test coverage
- **Then** G6 fails with `missing_test_for: ["AC-3"]`, the run loops back to DEVELOP (loop 1 of 2), and the Developer receives the gap report.

#### Evidence capture: screenshot

- **Given** the target app has a UI change
- **When** the Verify agent runs Playwright
- **Then** at least one PNG screenshot is captured and saved to `runs/<run_id>/evidence/`, and the path is included in the verification report.

#### Evidence capture: API response

- **Given** the implementation adds a new REST endpoint
- **When** the Verify agent makes an HTTP request to the endpoint
- **Then** the full response payload (status, headers, body) is captured to `runs/<run_id>/evidence/api_responses/` as a JSON artifact.

#### Verify→Develop loop exhausted

- **Given** G6 has failed twice (both DEVLOP↔VERIFY loops consumed)
- **When** the orchestrator checks the loop counter
- **Then** the run transitions to FAILED with the last verification failure preserved.

---

## Capability: `review-agent`

Independently reviews the git diff against acceptance criteria, security standards, integrity, performance, and conventions. Produces a severity-ranked verdict that gates progression to PR.

### Requirements

- **REVW-REQ-1**: The system SHALL run the Review agent in a fresh, independent session — receiving only the git diff, acceptance criteria, and project conventions. It SHALL NOT receive the Developer's reasoning, prompts, or session history.
- **REVW-REQ-2**: The system SHALL review the diff across five dimensions in priority order: (1) Security, (2) Integrity, (3) Performance, (4) Architecture/Conventions, (5) Code Quality.
- **REVW-REQ-3**: The system SHALL classify each finding with a severity level: `CRITICAL` (blocks approval), `WARNING` (should fix), `SUGGESTION` (optional improvement), or `OK` (no issue).
- **REVW-REQ-4**: The system SHALL annotate every finding with `file`, `line`, `severity`, `category`, and a concrete, actionable `fix` description.
- **REVW-REQ-5**: The system SHALL produce a verdict: `APPROVED` (no CRITICAL findings), `APPROVED_WITH_SUGGESTIONS` (WARNINGs/SUGGESTIONs only), or `CHANGES_REQUIRED` (≥1 CRITICAL).
- **REVW-REQ-6**: The system SHALL pass G7 only when `verdict ∈ {APPROVED, APPROVED_WITH_SUGGESTIONS}`. `CHANGES_REQUIRED` loops back to DEVELOP (not retry Review itself).
- **REVW-REQ-7**: The system SHALL loop DEVELOP↔REVIEW up to 2 times. After 2 loops, if G7 still fails, the run transitions to FAILED.
- **REVW-REQ-8**: The system SHALL specifically check for: hardcoded secrets, SQL injection, XSS vectors, missing input validation, stack traces in error responses, authentication bypasses, N+1 queries, missing transaction handling, swallowed exceptions, and sync-over-async patterns.
- **REVW-REQ-9**: The system SHALL operate in read-only mode on the repository — no edits allowed during review.

### Scenarios

#### Review approves clean code

- **Given** a git diff with no security issues, clean architecture, and passing tests
- **When** the Review agent inspects the diff
- **Then** findings are all `OK` or `SUGGESTION`, `verdict: APPROVED`, and G7 passes.

#### Review finds CRITICAL security issue

- **Given** the Developer committed a hardcoded API key in `src/config.ts` at line 42
- **When** the Review agent scans the diff
- **Then** it produces a finding: `{severity: CRITICAL, file: "src/config.ts", line: 42, category: "security", fix: "Move API key to environment variable"}`, `verdict: CHANGES_REQUIRED`, and the run loops back to DEVELOP.

#### Review approves with suggestions

- **Given** the diff has no CRITICAL or WARNING findings, but 3 SUGGESTIONs (e.g., variable naming, redundant import)
- **When** the Review agent evaluates the diff
- **Then** `verdict: APPROVED_WITH_SUGGESTIONS`, G7 passes, and the suggestions are preserved in the review artifact for the PR body.

#### Develop→Review loop exhausted

- **Given** G7 has failed twice (both DEVLOP↔REVIEW loops consumed) with CHANGES_REQUIRED
- **When** the orchestrator checks the loop counter
- **Then** the run transitions to FAILED with the last review verdict and CRITICAL findings preserved.

---

## Capability: `pr-agent`

Pushes the feature branch, runs a pre-push secret scan, and opens a real Pull Request against the target repository with an auto-generated body containing evidence links.

### Requirements

- **PR-REQ-1**: The system SHALL run a secret scan on the git diff before pushing — if any secrets are detected, G8 fails and the push is blocked.
- **PR-REQ-2**: The system SHALL push the feature branch to the remote repository. It SHALL NOT force-push or push to a protected branch.
- **PR-REQ-3**: The system SHALL open a PR via the appropriate Git provider CLI/API (GitHub via `gh`, GitLab via REST API, Bitbucket via REST API), abstracted behind a `GitProvider` interface.
- **PR-REQ-4**: The system SHALL auto-generate a PR body containing: summary of changes, link to the source Jira ticket, list of modified files, test results summary, link to evidence artifacts (screenshots, API responses), and review findings.
- **PR-REQ-5**: The system SHALL discover the Git provider type from the remote URL (github.com → GitHub, gitlab.com → GitLab, bitbucket.org → Bitbucket) and select the correct adapter.
- **PR-REQ-6**: The system SHALL pass G8 only when: all previous gates (G1–G7) are green, the secret scan is clean, HITL approval has been granted (if enabled), and the PR was opened successfully.
- **PR-REQ-7**: The system SHALL NOT open a PR against the Agent Factory repository itself — only against the configured target repository.
- **PR-REQ-8**: The system SHALL preserve the PR URL in the run artifact for dashboard display.

### Scenarios

#### PR opened successfully

- **Given** all gates G1–G7 are green, secret scan is clean, HITL is approved, and the remote is GitHub
- **When** the PR agent runs
- **Then** the branch is pushed, `gh pr create` is called with auto-generated body, the PR URL is returned, G8 passes, and the run transitions to DONE.

#### Secret scan blocks PR

- **Given** the git diff contains an AWS access key pattern
- **When** the secret scan runs
- **Then** the scan detects the secret, G8 fails, the push is blocked, and the run transitions to FAILED with `secret_scan: {detected: ["aws_access_key in src/config.ts:12"]}`.

#### GitLab provider detection

- **Given** the remote URL is `git@gitlab.com:team/project.git`
- **When** the PR agent discovers the provider
- **Then** it selects the GitLab adapter and uses the GitLab REST API to create a merge request.

#### Auto-generated PR body

- **Given** a complete run with test results, 2 screenshots, and review findings of 3 SUGGESTIONs
- **When** the PR body is generated
- **Then** it contains: a `## Summary` section, `## Changes` with file list, `## Tests` with pass/fail counts, `## Evidence` with screenshot links, `## Review` with finding count, and `## Ticket` with Jira link.

---

## Capability: `dashboard-ui`

Single-page React application providing real-time pipeline visualization, SSE streaming per role, evidence panel, ticket submission form, and dark/light mode — all rendered from Pencil MCP designs with a Hallmark-compliant design system.

### Requirements

- **DASH-REQ-1**: The system SHALL display a pipeline stepper showing all 8 phases (Intake → Spec → Design → Tasks → Develop → Verify → Review → PR) with real-time status per phase: PENDING, ACTIVE, PASSED, FAILED, BOUNCED.
- **DASH-REQ-2**: The system SHALL receive SSE events from the backend and update the stepper and role output panels in real time without page refresh.
- **DASH-REQ-3**: The system SHALL display role streaming output in a per-role panel that shows live text chunks as they arrive from the backend, labeled by phase.
- **DASH-REQ-4**: The system SHALL provide an evidence panel with tabs for: Tests (test results per AC), API Responses (captured JSON payloads), Screenshots (PNG images), and Review (findings list).
- **DASH-REQ-5**: The system SHALL display a PR summary card upon completion: PR URL, branch name, files changed count, test pass/fail summary, and review verdict.
- **DASH-REQ-6**: The system SHALL provide a ticket submission form with fields: title, description, acceptance criteria (dynamic Given-When-Then rows), priority, and components. The form SHALL validate required fields before submission.
- **DASH-REQ-7**: The system SHALL implement a Hallmark-compliant design system: OKLCH color palette, paired display/body typography, ×4 spacing scale, asymmetric layout. Components SHALL be generated from Pencil MCP .pen files.
- **DASH-REQ-8**: The system SHALL support dark mode and light mode, toggled via UI control, with smooth color transitions.
- **DASH-REQ-9**: The system SHALL display the budget tracker: accumulated token usage and estimated cost per run, updated in real time.
- **DASH-REQ-10**: The system SHALL display the audit trail: a chronological list of events (phase transitions, gate results, retries, errors) for the currently viewed run.
- **DASH-REQ-11**: The system SHALL support multiple concurrent runs — each with its own stepper, streaming, and evidence panel — switchable via a run selector.
- **DASH-REQ-12**: The system SHALL handle SSE disconnection gracefully: display a reconnecting indicator, auto-reconnect with EventSource, and resume state from the last received event.

### Scenarios

#### Live pipeline visualization

- **Given** a new run has been submitted and the dashboard is open
- **When** the backend emits SSE events for INTAKE→SPEC→DESIGN phase transitions
- **Then** the pipeline stepper updates each phase status from PENDING to ACTIVE to PASSED in real time, and the corresponding role output panel shows streaming text.

#### Gate failure display

- **Given** the G3 (Develop) gate fails
- **When** the backend emits a `gate_failed` SSE event
- **Then** the pipeline stepper shows DEVELOP phase as FAILED (red), the gate status card shows the failure reason, and the retry indicator appears showing "Retry 1 of 2".

#### Evidence panel: screenshots tab

- **Given** the Verify phase has completed with 2 screenshots captured
- **When** the user clicks the "Screenshots" tab in the evidence panel
- **Then** both PNG images are displayed inline with their capture timestamps and descriptions.

#### Ticket form validation

- **Given** the user opens the ticket submission form
- **When** the user submits without filling acceptance criteria
- **Then** the form shows a validation error "At least one acceptance criterion is required" and does NOT submit.

#### Dark mode toggle

- **Given** the dashboard is in light mode
- **When** the user clicks the dark mode toggle
- **Then** all components transition to the dark color scheme: background becomes dark, text becomes light, OKLCH colors shift to their dark-mode variants, and the preference is persisted to localStorage.

#### Budget tracker update

- **Given** a run has consumed 45,000 tokens across Intake and Spec phases
- **When** the backend emits a `budget_update` SSE event with `tokens: 45000, cost_usd: 0.063`
- **Then** the budget tracker in the dashboard updates to show the new totals in real time.

---

## Gate Reference

| Gate | Phase Guard | Pass Condition | Fail Action |
|------|-------------|---------------|-------------|
| **G1** | Intake → Spec | `completeness_score ≥ 80` | BOUNCED — return score + missing fields to user |
| **G2** | Spec → Design | All ACs covered by specs, spec schema valid | Retry Spec (×1) → FAILED |
| **G3** | Design → Tasks | All `files_referenced` exist on disk, all ACs covered | Retry Design (×1) → FAILED |
| **G4** | Tasks → Develop | All spec requirements mapped to tasks, no circular deps | Retry Tasks (×1) → FAILED |
| **G5** | Develop → Verify | `git diff` ≠ empty, build=0, lint=0 | Retry Develop (×2) → FAILED |
| **G6** | Verify → Review | ≥1 test per AC, suite passes, ≥1 screenshot | Loop→Develop (×2) → FAILED |
| **G7** | Review → PR | Verdict ∈ {APPROVED, APPROVED_WITH_SUGGESTIONS} | Loop→Develop (×2) → FAILED |
| **G8** | PR → DONE | Secret-scan clean, HITL approved, PR opened | FAILED |

---

## Transversal Guardrails

| Guardrail | Requirement | Scope |
|-----------|------------|-------|
| **Budget tracking** | Accumulate token usage + cost per run, display in dashboard. Cut to FAILED on exhaust (if cap configured). No default cap in MVP. | All phases |
| **Scope guard** | Advisory: log warning when Developer edits outside declared `components[]`. Do NOT deny the edit. | Develop |
| **Secret scanning** | Pre-push scan of git diff. Block push + FAIL run on detection. | PR |
| **HITL pause** | Configurable. When ON, pause at `PR_READY` state. Require `/approve` API call to proceed. | PR |
| **Audit trail** | Immutable event log per run: phase_start, phase_end, gate_eval, retry, error, budget_exceeded. Seq per run. | All phases |
| **Anti-hallucination** | G3 validates `files_referenced` paths with `os.path.exists()`. Cannot pass without real file existence. | Design |
| **Independent sessions** | Verify and Review receive NO developer context. Fresh sessions per role execution. | Verify, Review |
