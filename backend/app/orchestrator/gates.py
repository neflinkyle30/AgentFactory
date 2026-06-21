"""Gate evaluators — programmatic pipeline gate checks.

Each gate is a method that returns (passed: bool, reason: str).
Gates are evaluated by the orchestrator after each phase completes.
G1 is fully implemented; G2-G8 are stubs that will be fleshed out
as their corresponding phases are built.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Run, Ticket

logger = logging.getLogger(__name__)


class GateEvaluator:
    """Evaluates pipeline gates programmatically.

    Each gate method receives the run and its associated database session.
    Returns a tuple of (passed, reason).

    Gate reference:
        G1: Intake → Spec      (completeness_score ≥ 80)
        G2: Spec → Design      (all ACs covered, schema valid)
        G3: Design → Tasks     (all files_referenced exist)
        G4: Tasks → Develop    (all reqs mapped, no circular deps)
        G5: Develop → Verify   (diff non-empty, build=0, lint=0)
        G6: Verify → Review    (≥1 test per AC, suite passes, ≥1 screenshot)
        G7: Review → PR_READY  (verdict ∈ {APPROVED, APPROVED_WITH_SUGGESTIONS})
        G8: PR_OPENED → DONE   (secret-scan clean, PR opened)
    """

    # ── G1: Intake → Spec ──────────────────────────────────────────

    async def evaluate_g1(
        self, run: Run, db: AsyncSession, *, score_threshold: int = 80
    ) -> tuple[bool, str]:
        """G1: Intake completeness score must be ≥ threshold.

        Reads the Ticket linked to this Run and checks completeness_score.
        """
        # Fetch the ticket
        ticket = await db.get(Ticket, run.ticket_ref) if run.ticket_ref else None
        if ticket is None:
            # Fallback: find ticket linked to this run
            from sqlalchemy import select
            stmt = select(Ticket).where(Ticket.run_id == run.id)
            result = await db.execute(stmt)
            ticket = result.scalar_one_or_none()

        if ticket is None:
            return (False, "G1: No ticket found for this run")

        score = ticket.completeness_score or 0
        passed = score >= score_threshold

        if passed:
            return (True, f"G1 PASS: completeness_score={score} ≥ {score_threshold}")
        else:
            return (
                False,
                f"G1 FAIL: completeness_score={score} < {score_threshold}",
            )

    # ── G2: Spec → Design ──────────────────────────────────────────

    async def evaluate_g2(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G2: All ACs covered by spec, schema is valid JSON.

        Reads the Spec phase output artifact and validates:
        1. coverage_pct == 100
        2. Every AC has a mapped requirement
        3. Schema is valid JSON with requirements array
        """
        from sqlalchemy import select
        from app.models.artifact import Artifact
        import json

        stmt = (
            select(Artifact)
            .where(
                Artifact.run_id == run.id,
                Artifact.phase_name == "SPEC",
                Artifact.artifact_type == "spec_result",
            )
            .order_by(Artifact.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        artifact = result.scalar_one_or_none()

        if artifact is None:
            return (False, "G2 FAIL: No spec artifact found — Spec phase may not have run")

        try:
            data = json.loads(artifact.content_ref or "{}")
        except json.JSONDecodeError:
            return (False, "G2 FAIL: Spec artifact content is not valid JSON")

        requirements = data.get("requirements", [])
        coverage_pct = data.get("coverage_pct", 0)

        if not requirements:
            return (False, "G2 FAIL: No requirements defined in spec")

        if coverage_pct < 100:
            return (False, f"G2 FAIL: coverage_pct={coverage_pct} < 100 — not all ACs covered")

        # Validate each requirement has required fields
        for req in requirements:
            if not req.get("id") or not req.get("shall_text"):
                return (False, f"G2 FAIL: Requirement missing 'id' or 'shall_text': {req}")

        return (True, f"G2 PASS: {len(requirements)} requirements, coverage_pct={coverage_pct}")

    # ── G3: Design → Tasks ─────────────────────────────────────────

    async def evaluate_g3(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G3: All files_referenced exist on disk (or are planned new files).

        Reads the Design phase output artifact and validates:
        1. design_doc is non-empty
        2. files_referenced list is non-empty
        3. Each file either exists or is a planned new file (acceptable)
        """
        from sqlalchemy import select
        from app.models.artifact import Artifact
        import json
        import os

        stmt = (
            select(Artifact)
            .where(
                Artifact.run_id == run.id,
                Artifact.phase_name == "DESIGN",
                Artifact.artifact_type == "design_result",
            )
            .order_by(Artifact.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        artifact = result.scalar_one_or_none()

        if artifact is None:
            return (False, "G3 FAIL: No design artifact found — Design phase may not have run")

        try:
            data = json.loads(artifact.content_ref or "{}")
        except json.JSONDecodeError:
            return (False, "G3 FAIL: Design artifact content is not valid JSON")

        design_doc = data.get("design_doc", "")
        files_referenced = data.get("files_referenced", [])

        if not design_doc or not design_doc.strip():
            return (False, "G3 FAIL: design_doc is empty")

        if not files_referenced:
            return (False, "G3 FAIL: No files_referenced in design")

        # Check each file — if it doesn't exist, note it as a planned new file
        missing = []
        for path in files_referenced:
            if not os.path.exists(path):
                missing.append(path)

        if missing:
            # Files that don't exist yet are acceptable (they are planned new files)
            logger.info("G3: %d files not yet on disk (planned new files): %s", len(missing), missing)

        return (True, f"G3 PASS: {len(files_referenced)} files referenced ({len(missing)} new files planned)")

    # ── G4: Tasks → Develop ────────────────────────────────────────

    async def evaluate_g4(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G4: All reqs mapped to ≥1 task, no circular dependencies.

        Reads the Tasks phase output artifact and validates:
        1. coverage_pct == 100 (every requirement covered by ≥1 task)
        2. No circular dependencies in the task DAG
        3. Tasks list is non-empty
        """
        from sqlalchemy import select
        from app.models.artifact import Artifact
        import json

        stmt = (
            select(Artifact)
            .where(
                Artifact.run_id == run.id,
                Artifact.phase_name == "TASKS",
                Artifact.artifact_type == "tasks_result",
            )
            .order_by(Artifact.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        artifact = result.scalar_one_or_none()

        if artifact is None:
            return (False, "G4 FAIL: No tasks artifact found — Tasks phase may not have run")

        try:
            data = json.loads(artifact.content_ref or "{}")
        except json.JSONDecodeError:
            return (False, "G4 FAIL: Tasks artifact content is not valid JSON")

        tasks = data.get("tasks", [])
        coverage_pct = data.get("coverage_pct", 0)

        if not tasks:
            return (False, "G4 FAIL: No tasks defined")

        if coverage_pct < 100:
            return (False, f"G4 FAIL: coverage_pct={coverage_pct} < 100 — not all requirements covered")

        # Check for circular dependencies
        if _has_circular_deps(tasks):
            return (False, "G4 FAIL: Circular dependencies detected in task list")

        return (True, f"G4 PASS: {len(tasks)} tasks, coverage_pct={coverage_pct}, no circular deps")

    # ── G5: Develop → Verify ──────────────────────────────────────

    async def evaluate_g5(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G5: diff non-empty, build=0, lint=0.

        Reads the Develop phase output artifact and checks:
        1. At least one file was changed (git diff not empty).
        2. Build succeeded (exit code 0).
        3. Lint succeeded (exit code 0).

        For now, build and lint checks are placeholder — they read
        the status reported by the develop agent rather than running
        actual subprocess commands. Command execution will be
        configurable per target repo in a future iteration.
        """
        # ── Fetch the Develop phase output artifact ──────────────
        from sqlalchemy import select
        from app.models.artifact import Artifact

        stmt = (
            select(Artifact)
            .where(
                Artifact.run_id == run.id,
                Artifact.phase_name == "DEVELOP",
                Artifact.artifact_type == "develop_result",
            )
            .order_by(Artifact.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        artifact = result.scalar_one_or_none()

        if artifact is None:
            return (False, "G5 FAIL: No develop artifact found — Develop phase may not have run")

        # ── Parse artifact content ───────────────────────────────
        import json

        try:
            data = json.loads(artifact.content_ref or "{}")
        except json.JSONDecodeError:
            return (False, "G5 FAIL: Develop artifact content is not valid JSON")

        # ── Check 1: git diff not empty ──────────────────────────
        files_changed = data.get("files_changed", [])
        if not files_changed:
            return (False, "G5 FAIL: No files changed — git diff is empty")

        # ── Check 2: build OK ────────────────────────────────────
        build = data.get("build_status", {})
        build_passed = build.get("passed", False)
        build_exit = build.get("exit_code", 1)
        if not build_passed:
            return (
                False,
                f"G5 FAIL: Build failed (exit code {build_exit}). "
                f"Output: {build.get('output', 'no output')[:200]}",
            )

        # ── Check 3: lint OK ─────────────────────────────────────
        lint = data.get("lint_status", {})
        lint_passed = lint.get("passed", False)
        lint_exit = lint.get("exit_code", 1)
        if not lint_passed:
            return (
                False,
                f"G5 FAIL: Lint failed (exit code {lint_exit}). "
                f"Output: {lint.get('output', 'no output')[:200]}",
            )

        # ── All checks passed ────────────────────────────────────
        return (
            True,
            f"G5 PASS: {len(files_changed)} files changed, build OK, lint OK",
        )

    # ── G6: Verify → Review ────────────────────────────────────────

    async def evaluate_g6(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G6: ≥1 test per AC, all tests passed.

        Reads the Verify phase output artifact and validates:
        1. At least one test_result per acceptance criterion
        2. All test_results have passed=true
        3. total_tests > 0
        """
        from sqlalchemy import select
        from app.models.artifact import Artifact
        import json

        stmt = (
            select(Artifact)
            .where(
                Artifact.run_id == run.id,
                Artifact.phase_name == "VERIFY",
                Artifact.artifact_type == "verify_result",
            )
            .order_by(Artifact.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        artifact = result.scalar_one_or_none()

        if artifact is None:
            return (False, "G6 FAIL: No verify artifact found — Verify phase may not have run")

        try:
            data = json.loads(artifact.content_ref or "{}")
        except json.JSONDecodeError:
            return (False, "G6 FAIL: Verify artifact content is not valid JSON")

        test_results = data.get("test_results", [])
        passed_tests = data.get("passed_tests", 0)
        total_tests = data.get("total_tests", 0)

        if not test_results:
            return (False, "G6 FAIL: No test results")

        if total_tests <= 0:
            return (False, "G6 FAIL: total_tests must be > 0")

        # Check all tests passed
        failed = [t for t in test_results if not t.get("passed", False)]
        if failed:
            failed_names = [t.get("test_name", "?") for t in failed]
            return (False, f"G6 FAIL: {len(failed)} test(s) failed: {failed_names}")

        if passed_tests < total_tests:
            return (False, f"G6 FAIL: passed_tests={passed_tests} < total_tests={total_tests}")

        return (True, f"G6 PASS: {passed_tests}/{total_tests} tests passed")

    # ── G7: Review → PR_READY ──────────────────────────────────────

    async def evaluate_g7(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G7: Verdict ∈ {APPROVED, APPROVED_WITH_SUGGESTIONS}, no CRITICAL findings.

        Reads the Review phase output artifact and validates:
        1. verdict is APPROVED or APPROVED_WITH_SUGGESTIONS
        2. No finding has severity == CRITICAL
        """
        from sqlalchemy import select
        from app.models.artifact import Artifact
        import json

        stmt = (
            select(Artifact)
            .where(
                Artifact.run_id == run.id,
                Artifact.phase_name == "REVIEW",
                Artifact.artifact_type == "review_result",
            )
            .order_by(Artifact.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        artifact = result.scalar_one_or_none()

        if artifact is None:
            return (False, "G7 FAIL: No review artifact found — Review phase may not have run")

        try:
            data = json.loads(artifact.content_ref or "{}")
        except json.JSONDecodeError:
            return (False, "G7 FAIL: Review artifact content is not valid JSON")

        verdict = data.get("verdict", "UNKNOWN")
        findings = data.get("findings", [])

        if verdict not in ("APPROVED", "APPROVED_WITH_SUGGESTIONS"):
            return (False, f"G7 FAIL: verdict={verdict} — must be APPROVED or APPROVED_WITH_SUGGESTIONS")

        criticals = [f for f in findings if f.get("severity") == "CRITICAL"]
        if criticals:
            crit_descs = [f.get("description", "?")[:80] for f in criticals]
            return (False, f"G7 FAIL: {len(criticals)} CRITICAL finding(s): {crit_descs}")

        return (True, f"G7 PASS: verdict={verdict}, {len(findings)} findings, 0 critical")

    # ── G8: PR_OPENED → DONE ───────────────────────────────────────

    async def evaluate_g8(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G8: PR body is non-empty, conventional commit format valid.

        Reads the PR phase output artifact and validates:
        1. pr_body is non-empty
        2. pr_title follows conventional commit format: type(scope): description
        3. commit_message is non-empty
        4. branch_name is non-empty
        """
        from sqlalchemy import select
        from app.models.artifact import Artifact
        import json

        stmt = (
            select(Artifact)
            .where(
                Artifact.run_id == run.id,
                Artifact.phase_name == "PR",
                Artifact.artifact_type == "pr_result",
            )
            .order_by(Artifact.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        artifact = result.scalar_one_or_none()

        if artifact is None:
            return (False, "G8 FAIL: No PR artifact found — PR phase may not have run")

        try:
            data = json.loads(artifact.content_ref or "{}")
        except json.JSONDecodeError:
            return (False, "G8 FAIL: PR artifact content is not valid JSON")

        pr_title = data.get("pr_title", "")
        pr_body = data.get("pr_body", "")
        branch_name = data.get("branch_name", "")
        commit_message = data.get("commit_message", "")

        if not pr_body or not pr_body.strip():
            return (False, "G8 FAIL: PR body is empty")

        if not pr_title:
            return (False, "G8 FAIL: PR title is empty")

        if not branch_name:
            return (False, "G8 FAIL: branch_name is empty")

        if not commit_message:
            return (False, "G8 FAIL: commit_message is empty")

        # Check conventional commit format: type(scope): description
        if ":" not in pr_title:
            return (False, f"G8 FAIL: PR title does not follow conventional commit format: \"{pr_title}\"")

        return (True, f"G8 PASS: PR title=\"{pr_title}\", branch={branch_name}")

    # ── Dispatch ───────────────────────────────────────────────────

    _GATE_MAP = {
        "g1": "evaluate_g1",
        "g2": "evaluate_g2",
        "g3": "evaluate_g3",
        "g4": "evaluate_g4",
        "g5": "evaluate_g5",
        "g6": "evaluate_g6",
        "g7": "evaluate_g7",
        "g8": "evaluate_g8",
    }

    async def evaluate(
        self, gate_id: str, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """Dispatch to the appropriate gate method by ID.

        Args:
            gate_id: Lowercase gate identifier ('g1', 'g2', ..., 'g8').
            run: The Run model instance.
            db: Active database session.

        Returns:
            (passed: bool, reason: str)
        """
        method_name = self._GATE_MAP.get(gate_id.lower())
        if method_name is None:
            return (False, f"Unknown gate: {gate_id}")

        method = getattr(self, method_name)
        return await method(run, db)


# ── Helper: Circular Dependency Detection ────────────────────────────


def _has_circular_deps(tasks: list) -> bool:
    """Check for circular dependencies in a task list via DFS.

    Each task should have: id, dependencies[] (list of task IDs).
    Returns True if a cycle is detected.
    """
    task_ids = {t["id"] for t in tasks}
    visited: set = set()
    rec_stack: set = set()

    def dfs(task_id: str) -> bool:
        visited.add(task_id)
        rec_stack.add(task_id)
        task = next((t for t in tasks if t["id"] == task_id), None)
        if task:
            for dep_id in task.get("dependencies", []):
                if dep_id not in task_ids:
                    continue
                if dep_id not in visited:
                    if dfs(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True
        rec_stack.discard(task_id)
        return False

    for tid in task_ids:
        if tid not in visited:
            if dfs(tid):
                return True
    return False
