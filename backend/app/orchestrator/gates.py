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

    # ── G2: Spec → Design (stub) ───────────────────────────────────

    async def evaluate_g2(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G2: All ACs covered by spec, schema valid. (STUB)"""
        return (True, "G2 PASS (not yet implemented)")

    # ── G3: Design → Tasks (stub) ──────────────────────────────────

    async def evaluate_g3(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G3: All files_referenced exist on disk. (STUB)"""
        return (True, "G3 PASS (not yet implemented)")

    # ── G4: Tasks → Develop (stub) ─────────────────────────────────

    async def evaluate_g4(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G4: All reqs mapped to tasks, no circular deps. (STUB)"""
        return (True, "G4 PASS (not yet implemented)")

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

    # ── G6: Verify → Review (stub) ─────────────────────────────────

    async def evaluate_g6(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G6: ≥1 test per AC, suite passes, ≥1 screenshot. (STUB)"""
        return (True, "G6 PASS (not yet implemented)")

    # ── G7: Review → PR_READY (stub) ───────────────────────────────

    async def evaluate_g7(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G7: Verdict ∈ {APPROVED, APPROVED_WITH_SUGGESTIONS}. (STUB)"""
        return (True, "G7 PASS (not yet implemented)")

    # ── G8: PR_OPENED → DONE (stub) ────────────────────────────────

    async def evaluate_g8(
        self, run: Run, db: AsyncSession
    ) -> tuple[bool, str]:
        """G8: Secret-scan clean, HITL approved, PR opened. (STUB)"""
        return (True, "G8 PASS (not yet implemented)")

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
