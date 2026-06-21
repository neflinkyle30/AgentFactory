"""Orchestrator core — wires the state machine, roles, gates, and persistence.

The Orchestrator is the central execution engine. It creates runs,
dispatches phases to role implementations, evaluates gates, persists
state to the database, and emits SSE events for the dashboard.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AIProvider, Message
from app.config import settings
from app.models import Run, Phase, Ticket, Event, Artifact
from app.orchestrator.gates import GateEvaluator
from app.orchestrator.roles.intake import IntakeRole, TicketInput, IntakeResult
from app.orchestrator.roles.develop import DevelopRole, DevelopInput, DevelopResult
from app.orchestrator.scope_guard import ScopeGuard, ScopeWarning
from app.orchestrator.state_machine import PipelineModel, create_state_machine

logger = logging.getLogger(__name__)

# ── Phase list ──────────────────────────────────────────────────────

PHASE_ORDER: List[str] = [
    "INTAKE",
    "SPEC",
    "DESIGN",
    "TASKS",
    "DEVELOP",
    "VERIFY",
    "REVIEW",
    "PR",
]


class Orchestrator:
    """Central pipeline executor.

    Manages the lifecycle of a run: creates the run record, dispatches
    each phase to the appropriate role, evaluates gates programmatically,
    persists artifacts and events, and controls state transitions via
    the pipeline state machine.

    Usage:
        orchestrator = Orchestrator(db=session, provider=deepseek)
        result = await orchestrator.start_run(ticket_input)
    """

    def __init__(
        self,
        db: AsyncSession,
        provider: AIProvider,
        *,
        gate_evaluator: Optional[GateEvaluator] = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            db: Active async database session.
            provider: AI provider for role execution.
            gate_evaluator: Optional custom gate evaluator.
        """
        self._db = db
        self._provider = provider
        self._gate_evaluator = gate_evaluator or GateEvaluator()
        self._roles: Dict[str, Any] = {}
        self._scope_guard = ScopeGuard()
        self._init_roles()

    # ── Public API ─────────────────────────────────────────────────

    async def start_run(
        self,
        ticket_input: TicketInput,
        *,
        created_by: Optional[UUID] = None,
        team_id: Optional[UUID] = None,
        budget_limit_usd: float = 0.0,
        hitl_enabled: bool = True,
    ) -> Dict[str, Any]:
        """Create a new pipeline run and execute the Intake phase.

        Args:
            ticket_input: The raw ticket data from the API.
            created_by: UUID of the submitting user (optional for now).
            team_id: UUID of the team (optional for now).
            budget_limit_usd: Maximum budget in USD (0 = unlimited).
            hitl_enabled: Whether HITL approval is required before PR.

        Returns:
            Dict with run_id, status, ticket_id, intake_score, etc.
        """
        # ── Create the Run ──────────────────────────────────────
        run_id = uuid4()
        now = datetime.now(timezone.utc)

        run = Run(
            id=run_id,
            team_id=team_id or uuid4(),  # Placeholder until auth is wired
            created_by=created_by or uuid4(),
            ticket_ref=str(run_id),  # Self-reference until ticket is created
            status="INTAKE",
            current_phase="INTAKE",
            total_cost_usd=0.0,
            budget_limit_usd=budget_limit_usd if budget_limit_usd > 0 else None,
            hitl_enabled=hitl_enabled,
            retry_counts={},
        )
        self._db.add(run)

        # ── Create initial Phase row ────────────────────────────
        phase = Phase(
            run_id=run_id,
            phase_name="INTAKE",
            status="ACTIVE",
            started_at=now,
        )
        self._db.add(phase)

        # ── Record event ────────────────────────────────────────
        await self._record_event(run_id, "phase_started", {
            "phase": "INTAKE",
            "timestamp": now.isoformat(),
        })

        await self._db.flush()

        # ── Execute Intake ──────────────────────────────────────
        intake_role = self._roles.get("INTAKE")
        if intake_role is None:
            raise RuntimeError("Intake role not initialized")

        try:
            intake_result = await self._execute_intake(
                run=run,
                ticket_input=ticket_input,
                intake_role=intake_role,
            )
        except Exception as exc:
            logger.exception("Intake execution failed: %s", exc)
            await self._fail_run(run, f"Intake error: {exc}")
            return {
                "run_id": run_id,
                "status": "FAILED",
                "message": str(exc),
                "intake_passed": False,
            }

        # ── Persist Ticket ──────────────────────────────────────
        ticket = await intake_role.persist_ticket(
            result=intake_result,
            run_id=str(run_id),
            created_by=str(run.created_by),
            raw_ticket=ticket_input.raw_ticket or {},
            db=self._db,
        )

        # Update run with ticket ref
        run.ticket_ref = str(ticket.id)

        # ── Complete Intake phase ───────────────────────────────
        phase.status = "PASSED" if intake_result.passed else "FAILED"
        phase.completed_at = datetime.now(timezone.utc)
        phase.output = intake_result.to_dict()

        await self._record_event(run_id, "phase_completed", {
            "phase": "INTAKE",
            "passed": intake_result.passed,
            "score": intake_result.completeness_score,
        })

        # ── Evaluate G1 and transition ──────────────────────────
        passed, reason = await self._gate_evaluator.evaluate_g1(run, self._db)

        await self._record_event(run_id, "gate_eval", {
            "gate": "g1",
            "passed": passed,
            "reason": reason,
        })

        if passed:
            run.status = "SPEC"
            run.current_phase = "SPEC"
            message = f"Intake passed (score: {intake_result.completeness_score}). Proceeding to SPEC."
        else:
            run.status = "BOUNCED"
            run.current_phase = None
            message = (
                f"Ticket bounced (score: {intake_result.completeness_score}). "
                f"Missing: {', '.join(intake_result.missing) if intake_result.missing else 'none'}."
            )

            await self._record_event(run_id, "bounced", {
                "score": intake_result.completeness_score,
                "missing": intake_result.missing,
                "suggestions": intake_result.suggestions,
            })

        await self._db.flush()

        return {
            "run_id": run_id,
            "status": run.status,
            "ticket_id": ticket.id,
            "intake_score": intake_result.completeness_score,
            "intake_passed": intake_result.passed,
            "message": message,
        }

    async def execute_phase(self, run: Run, phase_name: str) -> Dict[str, Any]:
        """Execute a pipeline phase and evaluate its gate.

        Args:
            run: The Run model instance.
            phase_name: The phase to execute (SPEC, DESIGN, etc.).

        Returns:
            Dict with phase result, gate result, and next state.
        """
        # ── Create phase row ────────────────────────────────────
        now = datetime.now(timezone.utc)
        phase = Phase(
            run_id=run.id,
            phase_name=phase_name,
            status="ACTIVE",
            started_at=now,
        )
        self._db.add(phase)

        await self._record_event(run.id, "phase_started", {
            "phase": phase_name,
            "timestamp": now.isoformat(),
        })

        await self._db.flush()

        # ── Execute role ─────────────────────────────────────────
        role = self._roles.get(phase_name)
        if role is None:
            # Role not yet implemented — stub execution
            logger.info("Phase %s not yet implemented — skipping", phase_name)
            phase.status = "PASSED"
            phase.completed_at = datetime.now(timezone.utc)
            phase.output = {"stub": True, "phase": phase_name}
            await self._db.flush()
            return {
                "phase": phase_name,
                "passed": True,
                "output": phase.output,
                "message": f"{phase_name} stub — not yet implemented",
            }

        # ── DEVELOP phase: execute implementation ───────────────
        if phase_name == "DEVELOP":
            return await self._execute_develop(run, phase)

        # ── Stub for unimplemented phases ───────────────────────
        phase.status = "PASSED"
        phase.completed_at = datetime.now(timezone.utc)
        phase.output = {"stub": True, "phase": phase_name}
        await self._db.flush()
        return {
            "phase": phase_name,
            "passed": True,
            "output": phase.output,
            "message": f"{phase_name} stub — not yet implemented",
        }

    # ── Internal ────────────────────────────────────────────────────

    def _init_roles(self) -> None:
        """Initialize role implementations for each phase."""
        self._roles["INTAKE"] = IntakeRole(self._provider)
        self._roles["DEVELOP"] = DevelopRole(self._provider)
        # Other roles will be added in future PRs:
        # self._roles["SPEC"] = SpecRole(self._provider)
        # self._roles["DESIGN"] = DesignRole(self._provider, ...)
        # ...

    async def _execute_intake(
        self,
        run: Run,
        ticket_input: TicketInput,
        intake_role: IntakeRole,
    ) -> IntakeResult:
        """Execute the Intake role and record results."""
        result = await intake_role.evaluate(ticket_input, db=self._db)

        # Track cost
        if result.raw_response:
            cost = self._provider.calculate_cost(
                self._provider.count_tokens(ticket_input.description or ""),
                self._provider.count_tokens(result.raw_response),
            )
            run.total_cost_usd = float(run.total_cost_usd or 0) + cost

        return result

    async def _execute_develop(
        self,
        run: Run,
        phase: Phase,
    ) -> Dict[str, Any]:
        """Execute the Develop phase and evaluate G5.

        Args:
            run: The Run model instance.
            phase: The Phase model instance for DEVELOP.

        Returns:
            Dict with phase result, gate result, scope warnings, and next state.
        """
        develop_role = self._roles.get("DEVELOP")
        if develop_role is None:
            raise RuntimeError("Develop role not initialized")

        # ── Build DevelopInput from run context ─────────────────
        # Fetch the ticket for component context
        from app.models.ticket import Ticket

        stmt = select(Ticket).where(Ticket.run_id == run.id)
        result = await self._db.execute(stmt)
        ticket = result.scalar_one_or_none()

        declared_components = (
            list(ticket.components) if ticket and ticket.components else []
        )

        # Build placeholder design/task inputs from artifacts
        # In real pipeline, these come from SPEC/DESIGN/TASKS phases
        design_doc = "## Design\nDesign doc will be provided by SPEC/DESIGN phases (future PR)."
        task_list = "## Tasks\nTask list will be provided by TASKS phase (future PR)."

        workdir = f"{settings.runs_directory}/{run.id}/workdir"

        develop_input = DevelopInput(
            design_doc=design_doc,
            task_list=task_list,
            repo_state={"workdir": workdir, "branch": f"agent-factory/{str(run.id)[:8]}"},
            declared_components=declared_components,
            workdir=workdir,
        )

        # ── Execute the develop agent ───────────────────────────
        try:
            develop_result: DevelopResult = await develop_role.execute(
                develop_input, db=self._db
            )
        except Exception as exc:
            logger.exception("Develop execution failed: %s", exc)
            phase.status = "FAILED"
            phase.completed_at = datetime.now(timezone.utc)
            phase.output = {"error": str(exc)}
            await self._db.flush()

            await self._record_event(run.id, "phase_completed", {
                "phase": "DEVELOP",
                "passed": False,
                "error": str(exc),
            })

            await self._fail_run(run, f"Develop error: {exc}")
            return {
                "phase": "DEVELOP",
                "passed": False,
                "output": phase.output,
                "message": f"Develop failed: {exc}",
            }

        # ── Track cost ──────────────────────────────────────────
        if develop_result.raw_response:
            cost = self._provider.calculate_cost(
                self._provider.count_tokens(develop_input.design_doc + develop_input.task_list),
                self._provider.count_tokens(develop_result.raw_response),
            )
            run.total_cost_usd = float(run.total_cost_usd or 0) + cost

        # ── Persist artifact ────────────────────────────────────
        await develop_role.persist_artifact(
            result=develop_result,
            run_id=str(run.id),
            db=self._db,
        )

        # ── Run scope guard (advisory only) ─────────────────────
        scope_warnings: list[ScopeWarning] = []
        if declared_components:
            scope_warnings = self._scope_guard.check_all(
                develop_result.files_changed,
                declared_components,
            )

        # Log each scope warning to the events table
        for warning in scope_warnings:
            await self._record_event(run.id, "scope_advisory", warning.to_dict())
            logger.warning(warning.message)

        # ── Complete phase ──────────────────────────────────────
        phase.status = "PASSED"  # Phase completed successfully
        phase.completed_at = datetime.now(timezone.utc)
        phase.output = develop_result.to_dict()

        await self._record_event(run.id, "phase_completed", {
            "phase": "DEVELOP",
            "passed": True,
            "files_changed": len(develop_result.files_changed),
            "build_passed": develop_result.build_passed,
            "lint_passed": develop_result.lint_passed,
            "deviations": len(develop_result.deviations),
            "scope_warnings": len(scope_warnings),
        })

        # ── Evaluate G5 and transition ──────────────────────────
        g5_passed, g5_reason = await self._gate_evaluator.evaluate_g5(run, self._db)

        await self._record_event(run.id, "gate_eval", {
            "gate": "g5",
            "passed": g5_passed,
            "reason": g5_reason,
        })

        if g5_passed:
            run.status = "VERIFY"
            run.current_phase = "VERIFY"
        else:
            run.status = "FAILED"
            run.current_phase = None
            await self._fail_run(run, g5_reason)

        await self._db.flush()

        return {
            "phase": "DEVELOP",
            "passed": g5_passed,
            "output": develop_result.to_dict(),
            "scope_warnings": [w.to_dict() for w in scope_warnings],
            "gate_result": {"g5_passed": g5_passed, "g5_reason": g5_reason},
            "message": g5_reason,
        }

    async def _record_event(
        self,
        run_id: UUID,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Event:
        """Create an audit trail event for a run."""
        seq_stmt = select(func.coalesce(func.max(Event.seq), 0)).where(
            Event.run_id == run_id
        )
        seq_result = await self._db.execute(seq_stmt)
        next_seq = seq_result.scalar_one() + 1

        event = Event(
            run_id=run_id,
            seq=next_seq,
            event_type=event_type,
            payload=payload,
        )
        self._db.add(event)
        await self._db.flush()
        return event

    async def _fail_run(self, run: Run, reason: str) -> None:
        """Transition a run to FAILED and record the reason."""
        run.status = "FAILED"
        run.current_phase = None
        run.completed_at = datetime.now(timezone.utc)

        await self._record_event(run.id, "error", {
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Mark current phase as failed
        stmt = select(Phase).where(
            Phase.run_id == run.id, Phase.status == "ACTIVE"
        )
        result = await self._db.execute(stmt)
        active_phase = result.scalar_one_or_none()
        if active_phase:
            active_phase.status = "FAILED"
            active_phase.completed_at = datetime.now(timezone.utc)

        await self._db.flush()
