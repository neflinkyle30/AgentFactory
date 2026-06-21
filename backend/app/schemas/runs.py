"""Pydantic models for Run API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request Models ──────────────────────────────────────────────────


class AcceptanceCriterion(BaseModel):
    """A single acceptance criterion in Given-When-Then format."""

    given: str = Field(..., description="The precondition context")
    when: str = Field(..., description="The action or event")
    then: str = Field(..., description="The expected outcome")


class SubmitRunRequest(BaseModel):
    """Request to submit a new ticket and start a pipeline run."""

    title: str = Field(..., min_length=1, max_length=500, description="Ticket title")
    description: str = Field(default="", max_length=10000, description="Ticket description")
    acceptance_criteria: Optional[List[AcceptanceCriterion]] = Field(
        default=None, description="Acceptance criteria in Given-When-Then format"
    )
    priority: str = Field(default="medium", description="Priority: critical, high, medium, low")
    components: Optional[List[str]] = Field(
        default=None, description="Affected components/modules"
    )
    ticket_source: str = Field(default="form", description="Source: 'form' or 'jira'")
    ticket_key: Optional[str] = Field(default=None, description="Jira ticket key (if source=jira)")
    budget_limit_usd: Optional[float] = Field(
        default=None, ge=0.0, description="Maximum budget in USD (0 = unlimited)"
    )
    hitl_enabled: bool = Field(default=True, description="Enable human-in-the-loop approval before PR")


# ── Response Models ─────────────────────────────────────────────────


class PhaseStatus(BaseModel):
    """Status of a single pipeline phase."""

    phase_name: str
    status: str  # PENDING, ACTIVE, PASSED, FAILED
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    output: Optional[Dict[str, Any]] = None


class RunStatusResponse(BaseModel):
    """Detailed status of a pipeline run."""

    id: UUID
    status: str  # INTAKE, SPEC, ..., DONE, etc.
    current_phase: Optional[str] = None
    ticket_ref: Optional[str] = None
    total_cost_usd: float = 0.0
    budget_limit_usd: Optional[float] = None
    hitl_enabled: bool = True
    phases: List[PhaseStatus] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class RunListItem(BaseModel):
    """Summary of a run for list views."""

    id: UUID
    status: str
    current_phase: Optional[str] = None
    ticket_ref: Optional[str] = None
    total_cost_usd: float = 0.0
    created_at: Optional[datetime] = None


class RunListResponse(BaseModel):
    """Paginated list of runs."""

    runs: List[RunListItem]
    total: int
    limit: int
    offset: int


class SubmitRunResponse(BaseModel):
    """Response after submitting a new ticket."""

    run_id: UUID
    status: str
    ticket_id: Optional[UUID] = None
    intake_score: Optional[int] = None
    intake_passed: bool = False
    message: str = ""


# ── SSE Event Models ────────────────────────────────────────────────

class SSEEvent(BaseModel):
    """A single SSE event emitted during pipeline execution."""

    event: str  # phase_started, phase_completed, gate_passed, gate_failed, log, chunk
    run_id: UUID
    data: Dict[str, Any] = Field(default_factory=dict)
