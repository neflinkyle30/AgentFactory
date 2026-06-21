"""Shared test fixtures for Agent Factory backend tests.

Provides mock database sessions, mock AI providers, and factory
functions for creating test Run/Ticket/Phase data.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# ── Fake model classes for testing gates without a real database ─────
# These are lightweight stand-ins that mimic SQLAlchemy mapped attributes.


class FakeRun:
    """Fake Run model for unit testing gates.

    Provides the attributes GateEvaluator accesses: id, ticket_ref,
    status, current_phase, total_cost_usd, retry_counts.
    """

    def __init__(
        self,
        *,
        run_id: uuid.UUID | None = None,
        status: str = "INTAKE",
        current_phase: str | None = "INTAKE",
        ticket_ref: str | None = None,
        total_cost_usd: float = 0.0,
    ) -> None:
        self.id = run_id or uuid.uuid4()
        self.status = status
        self.current_phase = current_phase
        self.ticket_ref = ticket_ref
        self.total_cost_usd = total_cost_usd
        self.retry_counts: dict = {}
        self.created_by = uuid.uuid4()
        self.team_id = uuid.uuid4()


class FakeTicket:
    """Fake Ticket model for unit testing gates.

    Provides the attributes GateEvaluator accesses: id, run_id,
    completeness_score, title, description, acceptance_criteria,
    components, priority, raw_ticket.
    """

    def __init__(
        self,
        *,
        ticket_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        completeness_score: int = 0,
        title: str = "Test Ticket",
        description: str = "",
        acceptance_criteria: list | None = None,
        components: list | None = None,
        priority: str = "medium",
    ) -> None:
        self.id = ticket_id or uuid.uuid4()
        self.run_id = run_id
        self.completeness_score = completeness_score
        self.title = title
        self.description = description
        self.acceptance_criteria = acceptance_criteria or []
        self.components = components or []
        self.priority = priority
        self.raw_ticket: dict = {}
        self.created_by = uuid.uuid4()


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def fake_run() -> FakeRun:
    """A basic FakeRun in INTAKE state with random UUIDs."""
    return FakeRun(
        status="INTAKE",
        current_phase="INTAKE",
    )


@pytest.fixture
def fake_ticket_high_score() -> FakeTicket:
    """A FakeTicket with completeness_score=88 (passes G1)."""
    return FakeTicket(
        completeness_score=88,
        title="Add dark mode toggle",
        description="Allow users to switch themes with localStorage persistence.",
        acceptance_criteria=[{"given": "user is on dashboard", "when": "click toggle", "then": "theme switches"}],
        components=["frontend", "design-system"],
        priority="medium",
    )


@pytest.fixture
def fake_ticket_low_score() -> FakeTicket:
    """A FakeTicket with completeness_score=42 (fails G1)."""
    return FakeTicket(
        completeness_score=42,
        title="",
        description="",
        priority="low",
    )


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """A MagicMock wrapping AsyncSession for gate tests.

    Returns a mock that can be configured per-test via side_effect
    on `.get()`, `.execute()`, etc.
    """
    session = AsyncMock(spec=AsyncSession)
    session.get = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_provider():
    """A mock AI provider that returns controlled responses.

    Uses the existing MockProvider from app.adapters.mock for
    deterministic testing.
    """
    from app.adapters.mock import MockProvider

    return MockProvider()
