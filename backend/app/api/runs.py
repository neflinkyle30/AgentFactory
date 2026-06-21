"""Run API endpoints — submit tickets, check status, stream events."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_provider
from app.adapters.base import AIProvider
from app.config import settings
from app.database import get_db
from app.models import Phase, Run, Ticket, Event
from app.orchestrator.gates import GateEvaluator
from app.orchestrator.roles.intake import IntakeRole, TicketInput, IntakeResult
from app.orchestrator.orchestrator import Orchestrator
from app.orchestrator.state_machine import PipelineModel, create_state_machine
from app.schemas.runs import (
    SubmitRunRequest,
    SubmitRunResponse,
    RunStatusResponse,
    RunListItem,
    RunListResponse,
    PhaseStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runs", tags=["runs"])

# ── Provider (cached) ───────────────────────────────────────────────

_provider: Optional[AIProvider] = None


def _get_provider() -> AIProvider:
    global _provider
    if _provider is None:
        _provider = get_provider()
    return _provider


# ── Orchestrator (cached) ───────────────────────────────────────────

_orchestrator: Optional[Orchestrator] = None


def _get_orchestrator(db: AsyncSession) -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(db=db, provider=_get_provider())
    else:
        _orchestrator._db = db  # Update session
        _orchestrator._provider = _get_provider()
    return _orchestrator


# ── POST /api/runs ──────────────────────────────────────────────────


@router.post("", response_model=SubmitRunResponse, status_code=201)
async def submit_run(
    body: SubmitRunRequest,
    db: AsyncSession = Depends(get_db),
) -> SubmitRunResponse:
    """Submit a new ticket and start the pipeline.

    Creates a Run and Ticket, runs the Intake agent, evaluates G1,
    and returns the result. If the ticket scores ≥ 80, the run
    proceeds to SPEC; otherwise it bounces back with feedback.
    """
    provider = _get_provider()
    orchestrator = Orchestrator(db=db, provider=provider)

    # Create the ticket input
    ticket_input = TicketInput(
        title=body.title,
        description=body.description,
        acceptance_criteria=(
            [ac.model_dump() for ac in body.acceptance_criteria]
            if body.acceptance_criteria
            else None
        ),
        priority=body.priority,
        components=body.components,
        ticket_source=body.ticket_source,
        ticket_key=body.ticket_key,
        raw_ticket=body.model_dump(),
    )

    # Start a run (creates Run row, triggers Intake, evaluates G1)
    try:
        result = await orchestrator.start_run(
            ticket_input=ticket_input,
            created_by=None,  # No auth yet — will be set when T-013 is wired
            budget_limit_usd=body.budget_limit_usd or settings.default_budget_limit_usd,
            hitl_enabled=body.hitl_enabled,
        )
    except Exception as exc:
        logger.exception("Failed to start run: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return SubmitRunResponse(
        run_id=result["run_id"],
        status=result["status"],
        ticket_id=result.get("ticket_id"),
        intake_score=result.get("intake_score"),
        intake_passed=result.get("intake_passed", False),
        message=result.get("message", ""),
    )


# ── GET /api/runs ───────────────────────────────────────────────────


@router.get("", response_model=RunListResponse)
async def list_runs(
    status: Optional[str] = Query(default=None, description="Filter by run status"),
    team_id: Optional[UUID] = Query(default=None, description="Filter by team"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> RunListResponse:
    """List runs with optional filtering and pagination.

    Returns runs ordered by creation time (newest first).
    """
    # Base query
    stmt = select(Run)

    if status:
        stmt = stmt.where(Run.status == status)
    if team_id:
        stmt = stmt.where(Run.team_id == team_id)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Fetch page
    stmt = stmt.order_by(Run.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    runs = result.scalars().all()

    items = [
        RunListItem(
            id=r.id,
            status=r.status,
            current_phase=r.current_phase,
            ticket_ref=r.ticket_ref,
            total_cost_usd=float(r.total_cost_usd) if r.total_cost_usd else 0.0,
            created_at=r.created_at,
        )
        for r in runs
    ]

    return RunListResponse(runs=items, total=total, limit=limit, offset=offset)


# ── GET /api/runs/{run_id} ──────────────────────────────────────────


@router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RunStatusResponse:
    """Get detailed status of a pipeline run including all phases."""
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    # Load phases
    from sqlalchemy.orm import selectinload
    stmt = select(Run).where(Run.id == run_id).options(selectinload(Run.phases))
    result = await db.execute(stmt)
    run = result.scalar_one()

    phases = [
        PhaseStatus(
            phase_name=p.phase_name,
            status=p.status,
            started_at=p.started_at,
            completed_at=p.completed_at,
            retry_count=p.retry_count,
            output=p.output,
        )
        for p in run.phases
    ]

    return RunStatusResponse(
        id=run.id,
        status=run.status,
        current_phase=run.current_phase,
        ticket_ref=run.ticket_ref,
        total_cost_usd=float(run.total_cost_usd) if run.total_cost_usd else 0.0,
        budget_limit_usd=float(run.budget_limit_usd) if run.budget_limit_usd else None,
        hitl_enabled=run.hitl_enabled,
        phases=phases,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


# ── GET /api/runs/{run_id}/stream ───────────────────────────────────


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE event stream for a pipeline run.

    Emits events: phase_started, phase_completed, gate_passed,
    gate_failed, log, and chunk (role output streaming).

    The client connects via EventSource and receives real-time
    updates as the pipeline progresses through phases.
    """
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        """Generate SSE events for the run's current state and progress."""
        # ── Replay existing events ──────────────────────────────
        stmt = (
            select(Event)
            .where(Event.run_id == run_id)
            .order_by(Event.seq.asc())
        )
        result = await db.execute(stmt)
        past_events = result.scalars().all()

        for evt in past_events:
            payload = evt.payload or {}
            payload["run_id"] = str(run_id)
            yield _sse_event(evt.event_type, payload)

        # ── Stream current phase progress ───────────────────────
        # For now, emit a status event showing current state
        phase_status = {
            "run_id": str(run_id),
            "status": run.status,
            "current_phase": run.current_phase,
        }
        yield _sse_event("status", phase_status)

        # If run is still active, poll for changes (simplified streaming)
        if run.status not in ("DONE", "FAILED", "BOUNCED", "AWAITING_HITL"):
            last_seq = max((e.seq for e in past_events), default=0)

            for _ in range(60):  # Poll for up to 60 seconds
                await asyncio.sleep(2)

                # Check for new events
                new_stmt = (
                    select(Event)
                    .where(Event.run_id == run_id, Event.seq > last_seq)
                    .order_by(Event.seq.asc())
                )
                new_result = await db.execute(new_stmt)
                new_events = new_result.scalars().all()

                for evt in new_events:
                    payload = evt.payload or {}
                    payload["run_id"] = str(run_id)
                    yield _sse_event(evt.event_type, payload)
                    last_seq = evt.seq

                # Check if run has reached a terminal state
                await db.refresh(run)
                if run.status in ("DONE", "FAILED", "BOUNCED"):
                    yield _sse_event("run_completed", {
                        "run_id": str(run_id),
                        "status": run.status,
                    })
                    break

        # Send done signal
        yield _sse_event("stream_end", {"run_id": str(run_id)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# ── POST /api/runs/{run_id}/approve ─────────────────────────────────


@router.post("/{run_id}/approve")
async def approve_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Approve a HITL-paused run at PR_READY.

    Transitions the run from AWAITING_HITL to PR_OPENED.
    """
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != "AWAITING_HITL":
        raise HTTPException(
            status_code=409,
            detail=f"Run is not awaiting approval (current status: {run.status})",
        )

    run.status = "PR_OPENED"
    run.current_phase = "PR_OPENED"

    # Record event
    seq_stmt = select(func.coalesce(func.max(Event.seq), 0)).where(
        Event.run_id == run_id
    )
    seq_result = await db.execute(seq_stmt)
    next_seq = seq_result.scalar_one() + 1

    event = Event(
        run_id=run_id,
        seq=next_seq,
        event_type="hitl_approved",
        payload={"approved_by": "api"},
    )
    db.add(event)

    await db.flush()
    return {"run_id": str(run_id), "status": run.status, "message": "Run approved"}


# ── SSE Helpers ─────────────────────────────────────────────────────


def _sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format a Server-Sent Event message."""
    json_data = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {json_data}\n\n"
