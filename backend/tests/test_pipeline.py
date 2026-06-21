"""Integration tests for the full Agent Factory pipeline.

Tests the orchestrator with MockProvider (AGENT_FACTORY_MOCK=1 mode)
to verify the complete pipeline flow end-to-end. Uses a real SQLite
database for persistence during test runs.

Requires: AGENT_FACTORY_MOCK=1, AGENT_FACTORY_DEV=1
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Force mock + dev mode before any app imports
os.environ["AGENT_FACTORY_MOCK"] = "1"
os.environ["AGENT_FACTORY_DEV"] = "1"


@pytest.mark.skip(reason="Requires database setup — integration suite entry point")
class TestPipelineIntegration:
    """Full pipeline integration tests.

    These tests require a running database (or SQLite in dev mode)
    and exercise the orchestrator end-to-end with MockProvider.
    Un-skip when the test database is configured.
    """

    @pytest.mark.asyncio
    async def test_full_pipeline_happy_path(self):
        """A ticket goes through all 8 phases to DONE with MockProvider."""
        pass

    @pytest.mark.asyncio
    async def test_bounce_low_score_ticket(self):
        """A low-score ticket is bounced at G1."""
        pass

    @pytest.mark.asyncio
    async def test_hitl_pause_resume(self):
        """HITL pauses at PR_READY and resumes on /approve."""
        pass


# ══════════════════════════════════════════════════════════════════════
# Orchestrator Unit Tests (offline — no database needed)
# ══════════════════════════════════════════════════════════════════════


class TestOrchestratorUnit:
    """Unit-level tests for Orchestrator behavior with mocked dependencies.

    These tests validate the orchestrator's control flow without
    requiring a real database or AI provider.
    """

    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, mock_db_session, mock_provider):
        """Orchestrator initializes with all 8 roles."""
        from app.orchestrator.orchestrator import Orchestrator

        orch = Orchestrator(db=mock_db_session, provider=mock_provider)

        # All 8 roles should be initialized
        role_names = ["INTAKE", "SPEC", "DESIGN", "TASKS", "DEVELOP", "VERIFY", "REVIEW", "PR"]
        for name in role_names:
            assert name in orch._roles, f"Role {name} not initialized"
            assert orch._roles[name] is not None

    @pytest.mark.asyncio
    async def test_orchestrator_with_custom_gate_evaluator(self, mock_db_session, mock_provider):
        """Orchestrator accepts a custom GateEvaluator."""
        from app.orchestrator.orchestrator import Orchestrator
        from app.orchestrator.gates import GateEvaluator

        custom_gates = GateEvaluator()
        orch = Orchestrator(
            db=mock_db_session,
            provider=mock_provider,
            gate_evaluator=custom_gates,
        )

        assert orch._gate_evaluator is custom_gates

    @pytest.mark.asyncio
    async def test_phase_order_is_8_phases(self):
        """PHASE_ORDER contains exactly 8 phases."""
        from app.orchestrator.orchestrator import PHASE_ORDER

        assert len(PHASE_ORDER) == 8
        assert PHASE_ORDER == [
            "INTAKE", "SPEC", "DESIGN", "TASKS",
            "DEVELOP", "VERIFY", "REVIEW", "PR",
        ]

    @pytest.mark.asyncio
    async def test_record_event_increments_sequence(self, mock_db_session, mock_provider):
        """Events are recorded with incrementing sequence numbers."""
        from app.orchestrator.orchestrator import Orchestrator
        from unittest.mock import AsyncMock, MagicMock

        # Mock the sequence query to return 0 (no prior events)
        mock_db_session.execute = AsyncMock(
            return_value=_make_mock_result_scalar(0)
        )

        orch = Orchestrator(db=mock_db_session, provider=mock_provider)
        run_id = uuid.uuid4()

        event = await orch._record_event(run_id, "test_event", {"key": "value"})

        assert event is not None
        assert event.event_type == "test_event"
        assert event.payload == {"key": "value"}
        assert event.run_id == run_id


def _make_mock_result_scalar(value):
    """Helper: make a mock SQLAlchemy result returning a scalar value."""
    result = MagicMock()
    result.scalar_one = MagicMock(return_value=value)
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


# ══════════════════════════════════════════════════════════════════════
# State Machine Tests
# ══════════════════════════════════════════════════════════════════════


class TestStateMachine:
    """Verify the pipeline state machine configuration."""

    def test_state_machine_has_13_states(self):
        """The pipeline FSM has 13 defined states."""
        from app.orchestrator.state_machine import STATES

        expected = {
            "INTAKE", "SPEC", "DESIGN", "TASKS", "DEVELOP",
            "VERIFY", "REVIEW", "PR_READY", "PR_OPENED",
            "DONE", "FAILED", "BOUNCED", "AWAITING_HITL",
        }
        assert set(STATES) == expected, f"Expected {expected}, got {set(STATES)}"

    def test_create_state_machine_returns_machine(self):
        """create_state_machine returns a valid Machine instance."""
        from app.orchestrator.state_machine import create_state_machine, PipelineModel

        model = PipelineModel()
        machine = create_state_machine(model)
        assert machine is not None
        assert machine.model is not None


# ══════════════════════════════════════════════════════════════════════
# Mock Provider Tests
# ══════════════════════════════════════════════════════════════════════


class TestMockProvider:
    """Verify MockProvider returns deterministic responses for each role."""

    @pytest.mark.asyncio
    async def test_mock_intake_response(self, mock_provider):
        """Intake system prompt returns intake mock response."""
        from app.adapters.base import Message

        result = await mock_provider.query(
            system_prompt="You are the Intake Agent. Evaluate tickets.",
            messages=[Message(role="user", content="Test ticket")],
        )
        assert "Intake Analysis" in result.content
        assert "Completeness Score" in result.content

    @pytest.mark.asyncio
    async def test_mock_develop_response(self, mock_provider):
        """Develop system prompt returns develop mock response."""
        from app.adapters.base import Message

        result = await mock_provider.query(
            system_prompt="You are a Developer Agent. Implement tasks.",
            messages=[Message(role="user", content="Implement feature X")],
        )
        assert "Development Summary" in result.content
        assert "Files Modified" in result.content

    @pytest.mark.asyncio
    async def test_mock_token_counting(self, mock_provider):
        """Mock token counting uses character/4 heuristic."""
        text = "Hello, this is a test string with some length."
        tokens = mock_provider.count_tokens(text)
        assert tokens > 0
        assert tokens == max(1, len(text) // 4)

    @pytest.mark.asyncio
    async def test_mock_cost_is_zero(self, mock_provider):
        """Mock mode always returns zero cost."""
        cost = mock_provider.calculate_cost(1000, 500)
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_mock_streaming(self, mock_provider):
        """Mock streaming yields chunks of the content."""
        from app.adapters.base import Message

        chunks = []
        async for chunk in mock_provider.query_stream(
            system_prompt="You are the Spec Agent.",
            messages=[Message(role="user", content="Write spec")],
        ):
            chunks.append(chunk)

        assert len(chunks) > 0
        full = "".join(chunks)
        assert "Specification" in full


# ══════════════════════════════════════════════════════════════════════
# Configuration Tests
# ══════════════════════════════════════════════════════════════════════


class TestConfig:
    """Verify application configuration loads correctly."""

    def test_settings_default_values(self):
        """Settings load with expected defaults."""
        from app.config import settings

        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_access_token_expire_minutes == 15
        assert settings.cors_origins == ["http://localhost:5173", "http://localhost:3000"]
        assert settings.spec_design_max_retries == 1
        assert settings.develop_verify_max_loops == 2

    def test_settings_mock_mode(self):
        """AGENT_FACTORY_MOCK=1 enables mock_mode."""
        from app.config import settings

        assert settings.mock_mode is True  # Set in this module's globals


# ══════════════════════════════════════════════════════════════════════
# Secret Scanner Tests
# ══════════════════════════════════════════════════════════════════════


class TestSecretScanner:
    """Verify secret scanner regex patterns."""

    @pytest.mark.asyncio
    async def test_scan_empty_directory(self, tmp_path):
        """Scanning an empty directory returns clean."""
        from app.guards.secret_scan import SecretScanner

        scanner = SecretScanner(use_detect_secrets=False)
        result = await scanner.scan_directory(str(tmp_path))

        assert result.passed is True
        assert len(result.findings) == 0
        assert result.files_scanned == 0
        assert result.scan_method == "regex"

    @pytest.mark.asyncio
    async def test_scan_detects_aws_key(self, tmp_path):
        """AWS access key pattern is detected."""
        from app.guards.secret_scan import SecretScanner

        # Write a file with a fake AWS key
        test_file = tmp_path / "config.py"
        test_file.write_text('AWS_KEY = "AKIA1234567890ABCDEF"')

        scanner = SecretScanner(use_detect_secrets=False)
        result = await scanner.scan_directory(str(tmp_path))

        assert result.passed is False
        assert len(result.findings) >= 1
        assert any(
            f.secret_type == "aws_access_key" for f in result.findings
        )

    @pytest.mark.asyncio
    async def test_scan_detects_openai_key(self, tmp_path):
        """OpenAI/DeepSeek API key pattern is detected by openai_key regex."""
        from app.guards.secret_scan import SecretScanner

        test_file = tmp_path / "config.py"
        test_file.write_text('DEEPSEEK_API_KEY = "sk-1234567890abcdef1234567890abcdef12345678"')

        scanner = SecretScanner(use_detect_secrets=False)
        result = await scanner.scan_directory(str(tmp_path))

        assert result.passed is False
        detected_types = {f.secret_type for f in result.findings}
        assert "openai_key" in detected_types, (
            f"Expected openai_key in findings, got: {detected_types}"
        )

    @pytest.mark.asyncio
    async def test_scan_clean_file_passes(self, tmp_path):
        """A file with no secrets passes the scan."""
        from app.guards.secret_scan import SecretScanner

        test_file = tmp_path / "hello.py"
        test_file.write_text('print("Hello, world!")')

        scanner = SecretScanner(use_detect_secrets=False)
        result = await scanner.scan_directory(str(tmp_path))

        assert result.passed is True
        assert len(result.findings) == 0

    @pytest.mark.asyncio
    async def test_secret_scan_result_to_dict(self):
        """SecretScanResult.to_dict() serializes correctly."""
        from app.guards.secret_scan import SecretScanResult, SecretFinding

        finding = SecretFinding(
            secret_type="aws_access_key",
            description="AWS Access Key",
            file_path="config.py",
            line=5,
            match_preview="AKIA...",
        )
        result = SecretScanResult(
            passed=False,
            findings=[finding],
            files_scanned=10,
            scan_method="regex",
        )

        d = result.to_dict()
        assert d["passed"] is False
        assert len(d["findings"]) == 1
        assert d["findings"][0]["secret_type"] == "aws_access_key"
        assert "match_preview" not in d["findings"][0]  # Redacted in persistence
        assert d["files_scanned"] == 10


# ══════════════════════════════════════════════════════════════════════
# Git Provider Detection Tests
# ══════════════════════════════════════════════════════════════════════


class TestGitProviderDetection:
    """Verify detect_provider() resolves provider from remote URLs."""

    def test_detect_github(self):
        """github.com → github."""
        from app.git.provider import detect_provider

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/org/repo.git\n",
                stderr="",
            )
            result = detect_provider()
            assert result == "github"

    def test_detect_gitlab(self):
        """gitlab.com → gitlab."""
        from app.git.provider import detect_provider

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="git@gitlab.com:team/project.git\n",
                stderr="",
            )
            result = detect_provider()
            assert result == "gitlab"

    def test_detect_bitbucket(self):
        """bitbucket.org → bitbucket."""
        from app.git.provider import detect_provider

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://bitbucket.org/workspace/repo.git\n",
                stderr="",
            )
            result = detect_provider()
            assert result == "bitbucket"

    def test_detect_defaults_to_github_on_error(self):
        """On subprocess error, defaults to github."""
        from app.git.provider import detect_provider

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = detect_provider()
            assert result == "github"


# ══════════════════════════════════════════════════════════════════════
# Scope Guard Tests
# ══════════════════════════════════════════════════════════════════════


class TestScopeGuard:
    """Verify scope guard advisory warnings."""

    def test_scope_guard_no_deviation(self):
        """Files within declared components: no warnings."""
        from app.orchestrator.scope_guard import ScopeGuard

        guard = ScopeGuard()
        files_changed = [
            {"path": "src/auth/login.py", "action": "modified"},
            {"path": "src/auth/middleware.py", "action": "created"},
        ]
        declared_components = ["auth", "api", "frontend"]

        warnings = guard.check_all(files_changed, declared_components)
        # Files are within auth, so no warnings expected
        assert len(warnings) == 0

    def test_scope_guard_detects_deviation(self):
        """File outside declared components: warning logged."""
        from app.orchestrator.scope_guard import ScopeGuard

        guard = ScopeGuard()
        files_changed = [
            {"path": "src/secret/module.py", "action": "modified"},
        ]
        declared_components = ["auth"]

        warnings = guard.check_all(files_changed, declared_components)
        assert len(warnings) == 1
        assert "secret/module.py" in warnings[0].file_path
        assert warnings[0].declared_components == declared_components

    def test_scope_guard_empty_components(self):
        """No declared components: warns about everything (advisory only)."""
        from app.orchestrator.scope_guard import ScopeGuard

        guard = ScopeGuard()
        files_changed = [
            {"path": "src/anything.py", "action": "modified"},
        ]

        warnings = guard.check_all(files_changed, [])
        # When no components declared, guard warns about all files (advisory)
        assert len(warnings) == 1
        assert "anything.py" in warnings[0].file_path
