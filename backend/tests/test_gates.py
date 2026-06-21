"""Unit tests for GateEvaluator — programmatic pipeline gate checks.

Tests all 8 gates (G1-G8) with mock Run, Ticket, and database sessions.
Each gate is tested for both pass and fail scenarios.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.orchestrator.gates import GateEvaluator, _has_circular_deps

# ── Helpers ──────────────────────────────────────────────────────────


def _make_mock_result(return_value, one_or_none: bool = True):
    """Create a mock SQLAlchemy Result that returns a scalar value."""
    result = MagicMock()
    if one_or_none:
        result.scalar_one_or_none = MagicMock(return_value=return_value)
    else:
        result.scalars = MagicMock()
        result.scalars().all = MagicMock(return_value=return_value)
    return result


def _make_artifact_json(data: dict) -> str:
    """Serialize a dict to JSON string for mock artifact content."""
    return json.dumps(data)


# ── Fake models (re-exported from conftest for readability) ──────────

from tests.conftest import FakeRun, FakeTicket


# ══════════════════════════════════════════════════════════════════════
# G1: Intake → Spec — completeness_score ≥ 80
# ══════════════════════════════════════════════════════════════════════


class TestGateG1:
    """G1: completeness_score ≥ 80 → PASS."""

    @pytest.mark.asyncio
    async def test_g1_score_88_passes(self, mock_db_session):
        """Score 88 ≥ 80: G1 passes."""
        run = FakeRun(ticket_ref="ticket-1234")
        ticket = FakeTicket(completeness_score=88)

        # Mock db.get to return the ticket directly
        mock_db_session.get = AsyncMock(return_value=ticket)

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g1(run, mock_db_session)

        assert passed is True
        assert "PASS" in reason
        assert "88" in reason
        assert "80" in reason

    @pytest.mark.asyncio
    async def test_g1_score_42_fails(self, mock_db_session):
        """Score 42 < 80: G1 fails."""
        run = FakeRun(ticket_ref="ticket-5678")
        ticket = FakeTicket(completeness_score=42)

        mock_db_session.get = AsyncMock(return_value=ticket)

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g1(run, mock_db_session)

        assert passed is False
        assert "FAIL" in reason
        assert "42" in reason

    @pytest.mark.asyncio
    async def test_g1_no_ticket_fails(self, mock_db_session):
        """No ticket found: G1 fails (edge case)."""
        run = FakeRun(ticket_ref=None)

        # Mock db.get returns None, and execute also returns None
        mock_db_session.get = AsyncMock(return_value=None)
        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(None)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g1(run, mock_db_session)

        assert passed is False
        assert "No ticket found" in reason

    @pytest.mark.asyncio
    async def test_g1_custom_threshold(self, mock_db_session):
        """Custom threshold: score 85 with threshold=90 fails."""
        run = FakeRun(ticket_ref="ticket-9999")
        ticket = FakeTicket(completeness_score=85)

        mock_db_session.get = AsyncMock(return_value=ticket)

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g1(
            run, mock_db_session, score_threshold=90
        )

        assert passed is False
        assert "90" in reason


# ══════════════════════════════════════════════════════════════════════
# G2: Spec → Design — all ACs covered, schema valid
# ══════════════════════════════════════════════════════════════════════


class TestGateG2:
    """G2: All ACs covered by spec, schema valid JSON."""

    @pytest.mark.asyncio
    async def test_g2_coverage_100_passes(self, mock_db_session):
        """100% coverage, valid schema: G2 passes."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "requirements": [
                {"id": "REQ-1", "shall_text": "The system SHALL do X"},
                {"id": "REQ-2", "shall_text": "The system SHALL do Y"},
            ],
            "coverage_pct": 100,
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g2(run, mock_db_session)

        assert passed is True
        assert "PASS" in reason
        assert "2 requirements" in reason

    @pytest.mark.asyncio
    async def test_g2_coverage_75_fails(self, mock_db_session):
        """75% coverage: G2 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "requirements": [{"id": "REQ-1", "shall_text": "X"}],
            "coverage_pct": 75,
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g2(run, mock_db_session)

        assert passed is False
        assert "coverage_pct=75" in reason

    @pytest.mark.asyncio
    async def test_g2_no_artifact_fails(self, mock_db_session):
        """No spec artifact: G2 fails."""
        run = FakeRun(run_id=uuid.uuid4())

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(None)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g2(run, mock_db_session)

        assert passed is False
        assert "No spec artifact" in reason

    @pytest.mark.asyncio
    async def test_g2_missing_req_fields_fails(self, mock_db_session):
        """Requirement missing 'id' or 'shall_text': G2 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "requirements": [
                {"id": "REQ-1"},  # Missing shall_text
            ],
            "coverage_pct": 100,
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g2(run, mock_db_session)

        assert passed is False
        assert "shall_text" in reason

    @pytest.mark.asyncio
    async def test_g2_empty_requirements_fails(self, mock_db_session):
        """Empty requirements array: G2 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "requirements": [],
            "coverage_pct": 100,
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g2(run, mock_db_session)

        assert passed is False
        assert "No requirements" in reason


# ══════════════════════════════════════════════════════════════════════
# G3: Design → Tasks — all files_referenced exist
# ══════════════════════════════════════════════════════════════════════


class TestGateG3:
    """G3: files_referenced exist on disk, design doc non-empty."""

    @pytest.mark.asyncio
    async def test_g3_valid_design_passes(self, mock_db_session):
        """Valid design with existing files: G3 passes."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "design_doc": "# Design\n\n## Architecture\n...",
            "files_referenced": [
                "/tmp/test_exists.txt",  # Will be checked by os.path.exists
            ],
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        # Mock os.path.exists to return True for the referenced file
        # (even if it doesn't exist — G3 accepts "planned new files")
        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g3(run, mock_db_session)

        assert passed is True
        assert "PASS" in reason

    @pytest.mark.asyncio
    async def test_g3_empty_design_doc_fails(self, mock_db_session):
        """Empty design_doc: G3 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "design_doc": "",
            "files_referenced": ["some_file.py"],
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g3(run, mock_db_session)

        assert passed is False
        assert "design_doc is empty" in reason

    @pytest.mark.asyncio
    async def test_g3_empty_files_fails(self, mock_db_session):
        """Empty files_referenced: G3 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "design_doc": "# Valid doc",
            "files_referenced": [],
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g3(run, mock_db_session)

        assert passed is False
        assert "No files_referenced" in reason

    @pytest.mark.asyncio
    async def test_g3_no_artifact_fails(self, mock_db_session):
        """No design artifact: G3 fails."""
        run = FakeRun(run_id=uuid.uuid4())

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(None)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g3(run, mock_db_session)

        assert passed is False
        assert "No design artifact" in reason


# ══════════════════════════════════════════════════════════════════════
# G4: Tasks → Develop — all reqs mapped, no circular deps
# ══════════════════════════════════════════════════════════════════════


class TestGateG4:
    """G4: All requirements mapped to tasks, no cycles."""

    @pytest.mark.asyncio
    async def test_g4_valid_tasks_passes(self, mock_db_session):
        """Valid task breakdown: G4 passes."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "tasks": [
                {"id": "T-001", "description": "Setup", "dependencies": []},
                {"id": "T-002", "description": "Implement", "dependencies": ["T-001"]},
                {"id": "T-003", "description": "Test", "dependencies": ["T-002"]},
            ],
            "coverage_pct": 100,
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g4(run, mock_db_session)

        assert passed is True
        assert "PASS" in reason

    @pytest.mark.asyncio
    async def test_g4_circular_deps_fails(self, mock_db_session):
        """Circular dependencies: G4 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "tasks": [
                {"id": "T-001", "dependencies": ["T-002"]},
                {"id": "T-002", "dependencies": ["T-001"]},
            ],
            "coverage_pct": 100,
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g4(run, mock_db_session)

        assert passed is False
        assert "Circular" in reason

    @pytest.mark.asyncio
    async def test_g4_incomplete_coverage_fails(self, mock_db_session):
        """Coverage < 100%: G4 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "tasks": [{"id": "T-001", "dependencies": []}],
            "coverage_pct": 50,
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g4(run, mock_db_session)

        assert passed is False
        assert "coverage_pct=50" in reason


# ══════════════════════════════════════════════════════════════════════
# G5: Develop → Verify — diff non-empty, build=0, lint=0
# ══════════════════════════════════════════════════════════════════════


class TestGateG5:
    """G5: diff non-empty, build OK, lint OK."""

    @pytest.mark.asyncio
    async def test_g5_clean_build_passes(self, mock_db_session):
        """Clean build and lint: G5 passes."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "files_changed": [
                {"path": "src/auth.py", "action": "modified"},
            ],
            "build_status": {"passed": True, "exit_code": 0},
            "lint_status": {"passed": True, "exit_code": 0},
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g5(run, mock_db_session)

        assert passed is True
        assert "PASS" in reason

    @pytest.mark.asyncio
    async def test_g5_empty_diff_fails(self, mock_db_session):
        """No files changed: G5 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "files_changed": [],
            "build_status": {"passed": True, "exit_code": 0},
            "lint_status": {"passed": True, "exit_code": 0},
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g5(run, mock_db_session)

        assert passed is False
        assert "No files changed" in reason

    @pytest.mark.asyncio
    async def test_g5_build_fails(self, mock_db_session):
        """Build failure: G5 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "files_changed": [{"path": "src/auth.py", "action": "modified"}],
            "build_status": {
                "passed": False,
                "exit_code": 1,
                "output": "SyntaxError: invalid syntax",
            },
            "lint_status": {"passed": True, "exit_code": 0},
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g5(run, mock_db_session)

        assert passed is False
        assert "Build failed" in reason

    @pytest.mark.asyncio
    async def test_g5_lint_fails(self, mock_db_session):
        """Lint failure: G5 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "files_changed": [{"path": "src/auth.py", "action": "modified"}],
            "build_status": {"passed": True, "exit_code": 0},
            "lint_status": {
                "passed": False,
                "exit_code": 1,
                "output": "unused variable: x",
            },
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g5(run, mock_db_session)

        assert passed is False
        assert "Lint failed" in reason


# ══════════════════════════════════════════════════════════════════════
# G6: Verify → Review — ≥1 test per AC, all passed
# ══════════════════════════════════════════════════════════════════════


class TestGateG6:
    """G6: All tests pass, at least one test per AC."""

    @pytest.mark.asyncio
    async def test_g6_all_passed_passes(self, mock_db_session):
        """All tests green: G6 passes."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "test_results": [
                {"test_name": "test_login", "passed": True, "ac_id": "AC-1"},
                {"test_name": "test_register", "passed": True, "ac_id": "AC-2"},
            ],
            "passed_tests": 2,
            "total_tests": 2,
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g6(run, mock_db_session)

        assert passed is True
        assert "PASS" in reason

    @pytest.mark.asyncio
    async def test_g6_failed_test_fails(self, mock_db_session):
        """A test failed: G6 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "test_results": [
                {"test_name": "test_login", "passed": True, "ac_id": "AC-1"},
                {"test_name": "test_register", "passed": False, "ac_id": "AC-2"},
            ],
            "passed_tests": 1,
            "total_tests": 2,
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g6(run, mock_db_session)

        assert passed is False
        assert "failed" in reason

    @pytest.mark.asyncio
    async def test_g6_no_tests_fails(self, mock_db_session):
        """No test results: G6 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "test_results": [],
            "passed_tests": 0,
            "total_tests": 0,
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g6(run, mock_db_session)

        assert passed is False
        assert "No test results" in reason


# ══════════════════════════════════════════════════════════════════════
# G7: Review → PR_READY — verdict ∈ {APPROVED, APPROVED_WITH_SUGGESTIONS}
# ══════════════════════════════════════════════════════════════════════


class TestGateG7:
    """G7: No CRITICAL findings, verdict approved."""

    @pytest.mark.asyncio
    async def test_g7_approved_passes(self, mock_db_session):
        """APPROVED verdict: G7 passes."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "verdict": "APPROVED",
            "findings": [
                {"severity": "SUGGESTION", "description": "Add docstring"},
            ],
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g7(run, mock_db_session)

        assert passed is True
        assert "PASS" in reason

    @pytest.mark.asyncio
    async def test_g7_approved_with_suggestions_passes(self, mock_db_session):
        """APPROVED_WITH_SUGGESTIONS: G7 passes."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "verdict": "APPROVED_WITH_SUGGESTIONS",
            "findings": [
                {"severity": "WARNING", "description": "Missing type hint"},
                {"severity": "SUGGESTION", "description": "Rename variable"},
            ],
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g7(run, mock_db_session)

        assert passed is True
        assert "PASS" in reason

    @pytest.mark.asyncio
    async def test_g7_changes_required_fails(self, mock_db_session):
        """CHANGES_REQUIRED verdict: G7 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "verdict": "CHANGES_REQUIRED",
            "findings": [
                {"severity": "CRITICAL", "description": "Hardcoded API key"},
            ],
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g7(run, mock_db_session)

        assert passed is False
        assert "verdict=CHANGES_REQUIRED" in reason

    @pytest.mark.asyncio
    async def test_g7_critical_finding_in_approved_fails(self, mock_db_session):
        """CRITICAL finding despite APPROVED: fails (defensive)."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "verdict": "APPROVED",
            "findings": [
                {"severity": "CRITICAL", "description": "SQL injection risk"},
            ],
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g7(run, mock_db_session)

        assert passed is False
        assert "CRITICAL" in reason


# ══════════════════════════════════════════════════════════════════════
# G8: PR_OPENED → DONE — PR body non-empty, conventional commit format
# ══════════════════════════════════════════════════════════════════════


class TestGateG8:
    """G8: PR artifact valid, conventional commit format."""

    @pytest.mark.asyncio
    async def test_g8_valid_pr_passes(self, mock_db_session):
        """Valid PR artifact: G8 passes."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "pr_title": "feat(dashboard): add dark mode toggle",
            "pr_body": "## Summary\n\nAdds dark mode support to the dashboard.",
            "branch_name": "agent-factory/dark-mode",
            "commit_message": "feat(dashboard): add dark mode toggle",
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g8(run, mock_db_session)

        assert passed is True
        assert "PASS" in reason

    @pytest.mark.asyncio
    async def test_g8_empty_pr_body_fails(self, mock_db_session):
        """Empty PR body: G8 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "pr_title": "feat: add feature",
            "pr_body": "",
            "branch_name": "feature/test",
            "commit_message": "feat: add feature",
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g8(run, mock_db_session)

        assert passed is False
        assert "PR body is empty" in reason

    @pytest.mark.asyncio
    async def test_g8_non_conventional_title_fails(self, mock_db_session):
        """PR title without colon: G8 fails."""
        run = FakeRun(run_id=uuid.uuid4())
        artifact = MagicMock()
        artifact.content_ref = _make_artifact_json({
            "pr_title": "Add dark mode",  # No colon, not conventional commit
            "pr_body": "## Summary\nChanges",
            "branch_name": "feature/dark-mode",
            "commit_message": "Add dark mode",
        })

        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result(artifact)
        )

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate_g8(run, mock_db_session)

        assert passed is False
        assert "conventional commit" in reason


# ══════════════════════════════════════════════════════════════════════
# Gate Dispatcher
# ══════════════════════════════════════════════════════════════════════


class TestGateDispatch:
    """The evaluate() dispatcher routes to correct gate methods."""

    @pytest.mark.asyncio
    async def test_dispatch_g1(self, mock_db_session):
        """evaluate('g1', ...) dispatches to evaluate_g1."""
        run = FakeRun(ticket_ref="t-1")
        ticket = FakeTicket(completeness_score=92)

        mock_db_session.get = AsyncMock(return_value=ticket)

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate("g1", run, mock_db_session)

        assert passed is True

    @pytest.mark.asyncio
    async def test_dispatch_unknown_gate(self, mock_db_session):
        """Unknown gate ID returns failure."""
        run = FakeRun()

        evaluator = GateEvaluator()
        passed, reason = await evaluator.evaluate("g99", run, mock_db_session)

        assert passed is False
        assert "Unknown gate" in reason


# ══════════════════════════════════════════════════════════════════════
# Helper: Circular Dependency Detection
# ══════════════════════════════════════════════════════════════════════


class TestCircularDeps:
    """_has_circular_deps() DFS cycle detection."""

    def test_no_cycle_linear_deps(self):
        """Linear deps: no cycle."""
        tasks = [
            {"id": "T1", "dependencies": []},
            {"id": "T2", "dependencies": ["T1"]},
            {"id": "T3", "dependencies": ["T2"]},
        ]
        assert _has_circular_deps(tasks) is False

    def test_cycle_detected(self):
        """T1→T2→T1: cycle detected."""
        tasks = [
            {"id": "T1", "dependencies": ["T2"]},
            {"id": "T2", "dependencies": ["T1"]},
        ]
        assert _has_circular_deps(tasks) is True

    def test_self_loop(self):
        """T1→T1: self-loop detected."""
        tasks = [
            {"id": "T1", "dependencies": ["T1"]},
        ]
        assert _has_circular_deps(tasks) is True

    def test_no_deps(self):
        """No dependencies at all: no cycle."""
        tasks = [
            {"id": "T1", "dependencies": []},
            {"id": "T2", "dependencies": []},
        ]
        assert _has_circular_deps(tasks) is False

    def test_external_dep_ignored(self):
        """Dependency references a task ID not in the list: ignored."""
        tasks = [
            {"id": "T1", "dependencies": ["T-EXTERNAL"]},
        ]
        assert _has_circular_deps(tasks) is False

    def test_diamond_dep_no_cycle(self):
        """Diamond pattern: no cycle."""
        tasks = [
            {"id": "T1", "dependencies": []},
            {"id": "T2", "dependencies": ["T1"]},
            {"id": "T3", "dependencies": ["T1"]},
            {"id": "T4", "dependencies": ["T2", "T3"]},
        ]
        assert _has_circular_deps(tasks) is False
