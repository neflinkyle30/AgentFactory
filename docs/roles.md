# Agent Factory OSS — Role Reference

## Overview

Agent Factory uses 8 independent AI roles, each with a dedicated system prompt, input/output schema, and programmatic gate. Roles execute sequentially — Verify and Review run as fresh sessions with NO developer context.

## Role Summary

| # | Role | Phase | Gate | Output |
|---|------|-------|------|--------|
| 1 | Intake | INTAKE | G1 (score≥80) | Normalized ticket + score |
| 2 | Spec | SPEC | G2 (all ACs covered) | Formal spec with GWT scenarios |
| 3 | Design | DESIGN | G3 (files exist) | Architecture doc + file plan |
| 4 | Tasks | TASKS | G4 (all reqs mapped) | Atomic task breakdown |
| 5 | Develop | DEVELOP | G5 (build=0, lint=0) | Code changes on branch |
| 6 | Verify | VERIFY | G6 (all tests pass) | Test report + evidence |
| 7 | Review | REVIEW | G7 (no CRITICAL) | Severity-ranked findings |
| 8 | PR Agent | PR | G8 (secret-scan clean) | PR body + metadata |

---

## 1. Intake Agent

**Purpose**: Validate incoming tickets against a completeness rubric. Score, normalize, and pass or bounce.

**Input**: Raw ticket data (Jira JSON or form submission).

**Output**: `IntakeResult` — normalized ticket, completeness_score (0-100), missing fields, suggestions.

**Gate (G1)**: `completeness_score ≥ 80`

**System Prompt Summary**:
- You are the Intake Agent for Agent Factory
- Validate every ticket against required template: title, description, ACs in Given-When-Then, priority, components
- Score on a deterministic rubric, not an LLM impression
- Produce canonical JSON with normalized fields
- Bounce tickets < 80 with actionable feedback

**Scoring Rubric**:
| Dimension | Max Points |
|-----------|-----------|
| AC presence and quality | 40 |
| Description clarity | 25 |
| Title specificity | 15 |
| Priority/sizing | 10 |
| Component identification | 10 |
| **Total** | **100** |

**Gate Threshold**: 80/100 → PASS. Below 80 → BOUNCED with missing[] and suggestions[].

---

## 2. Spec Agent

**Purpose**: Write formal requirements in Given-When-Then format. Every ticket AC must have at least one spec scenario.

**Input**: Normalized ticket from Intake.

**Output**: `SpecResult` — requirements[], scenarios[], coverage_map (AC→requirement mapping), coverage_pct.

**Gate (G2)**: All ACs mapped, spec JSON schema valid, coverage_pct = 100.

**System Prompt Summary**:
- You are the Specification Agent
- Write formal requirements using SHALL statements
- Every AC must map to ≥1 requirement
- Generate Granted-When-Then scenarios including edge cases
- Output structured JSON with id, shall_text, gwt, ac_id references
- Retry once on validation failure

---

## 3. Design Agent

**Purpose**: Explore the target repo (read-only), identify real files, and produce a technical design with file references that are PROGRAMMATICALLY validated to exist.

**Input**: Spec requirements + target repo path.

**Output**: `DesignResult` — design_doc, files_referenced[], components[], ac_coverage[].

**Gate (G3)**: All files_referenced exist on disk (or are planned new files), design_doc is non-empty, components[] is non-empty.

**System Prompt Summary**:
- You are the Design Agent
- Explore the target repository using Glob, Grep, Read (read-only)
- Identify real files, directories, and conventions
- Produce design.md with architecture decisions and rationale
- List files_referenced with absolute paths
- Mark unverified claims as [ASSUMPTION]
- Retry once if G3 fails (files don't exist)

---

## 4. Tasks Agent

**Purpose**: Break the design into atomic implementation tasks. Each task maps to specific files and ACs.

**Input**: Design document + spec requirements.

**Output**: `TasksResult` — tasks[] (each with id, description, files[], ac_ids[], estimated_complexity), coverage_pct.

**Gate (G4)**: All spec requirements mapped to ≥1 task, no circular dependencies, coverage_pct = 100.

**System Prompt Summary**:
- You are the Task Planner Agent
- Decompose the design into atomic, verifiable tasks
- Order by dependency: foundation before features, shared before specific
- Each task: id, description, target files, AC coverage, complexity estimate
- Detect and avoid circular dependencies
- Retry once on G4 failure

---

## 5. Develop Agent

**Purpose**: Implement the task plan on a fresh git branch. Write code, run builds, pass lint. Scope guard logs advisory warnings.

**Input**: Task list + design doc + target repo clone.

**Output**: `DevelopResult` — files_changed[], build_status, lint_status, deviations[].

**Gate (G5)**: `git diff` is non-empty, build exit code = 0, lint exit code = 0.

**System Prompt Summary**:
- You are the Developer Agent
- Clone repo to isolated working directory
- Create branch `agent-factory/<ticket-key>`
- Implement tasks sequentially, editing declared files
- Run build and lint after each batch
- Report build/lint results
- Respect scope boundaries (advisory warnings only)
- Retry up to 2 times if G5 fails

**Scope Guard**: Advisory only. If an edit touches a file outside declared components[], log warning with file, line, and component context. Do NOT deny the edit.

---

## 6. Verify Agent

**Purpose**: Independently validate the implementation against specs. Fresh session — NO developer context. Execute tests, capture evidence.

**Input**: Ticket + spec ACs + current repo state (NO developer reasoning).

**Output**: `VerifyResult` — test_results[] (per AC), screenshots[], api_responses[], verdict (PASSED/FAILED).

**Gate (G6)**: Every AC has ≥1 passing test, full suite passes, ≥1 screenshot captured.

**System Prompt Summary**:
- You are the Verification Agent
- Run FRESH session — you receive NO developer context
- Execute at least one test per acceptance criterion
- Capture ≥1 screenshot via Playwright
- Capture API response payloads as evidence
- Produce pass/fail verdict per AC
- On failure: loop back to DEVELOP (not retry Verify)
- Loop limit: 2 DEVELOP↔VERIFY cycles → FAILED

---

## 7. Review Agent

**Purpose**: Independently review the git diff. Fresh session. 5-dimension review with severity-ranked findings.

**Input**: Git diff + acceptance criteria + project conventions (NO developer reasoning).

**Output**: `ReviewResult` — findings[] (with severity, category, file, line), verdict (APPROVED/APPROVED_WITH_SUGGESTIONS/CHANGES_REQUIRED).

**Gate (G7)**: Verdict ∈ {APPROVED, APPROVED_WITH_SUGGESTIONS}. Any CRITICAL finding → CHANGES_REQUIRED.

**System Prompt Summary**:
- You are the Review Agent
- Run FRESH session — you receive NO developer context
- Review across 5 dimensions in priority order:
  1. Security (secrets, injection, auth bypasses)
  2. Integrity (data corruption, transaction handling)
  3. Performance (N+1 queries, sync-over-async)
  4. Architecture/Conventions (patterns, naming)
  5. Code Quality (readability, error handling)
- Classify: CRITICAL (blocks), WARNING (should fix), SUGGESTION (optional), OK
- On CHANGES_REQUIRED: loop back to DEVELOP
- Loop limit: 2 DEVELOP↔REVIEW cycles → FAILED

**Security Checks**:
- Hardcoded secrets/API keys
- SQL injection vectors
- XSS vectors
- Missing input validation
- Stack traces in error responses
- Authentication bypasses

---

## 8. PR Agent

**Purpose**: Generate PR metadata, run secret scan, and prepare the PR for creation.

**Input**: Diff summary + ticket data + review verdict.

**Output**: `PRAgentResult` — pr_title, pr_body, branch_name, commit_message.

**Gate (G8)**: PR body non-empty, conventional commit format, secret scan clean, HITL approved (if enabled).

**System Prompt Summary**:
- You are the PR Agent
- Generate PR title in conventional commit format: `type(scope): description`
- Auto-generate PR body with: Summary, Changes, Tests, Evidence, Review findings, Ticket link
- Run secret scan before push (G8 blocks on detection)
- Push to feature branch (never force-push)
- Create PR via Git provider

---

## Gate Thresholds Reference

| Gate | Guard | Threshold | Fail Action | Retry/Loop |
|------|-------|-----------|-------------|------------|
| G1 | Intake → Spec | score ≥ 80 | BOUNCED | 0 |
| G2 | Spec → Design | coverage = 100% | FAILED | Retry×1 |
| G3 | Design → Tasks | files exist | FAILED | Retry×1 |
| G4 | Tasks → Develop | coverage = 100%, no cycles | FAILED | Retry×1 |
| G5 | Develop → Verify | build=0, lint=0, diff≠∅ | FAILED | Retry×2 |
| G6 | Verify → Review | all tests pass, ≥1 screenshot | Loop→Develop | Loop×2 |
| G7 | Review → PR | no CRITICAL findings | Loop→Develop | Loop×2 |
| G8 | PR → DONE | secret-scan clean | FAILED | 0 |

## Fresh Session Guarantee

**Critical invariant**: Verify and Review agents MUST receive NO developer context.

The orchestrator enforces this by constructing fresh messages arrays for each role invocation. Verify and Review receive:
- The original ticket data
- The spec requirements and acceptance criteria
- The current repo state (files, diff)
- **Explicitly excluded**: Developer system prompts, reasoning, tool calls, or session history

This mirrors how a human reviewer works — they see the requirements and the code, not the developer's thought process.
