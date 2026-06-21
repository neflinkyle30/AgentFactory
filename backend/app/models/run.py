"""Run model — represents a single execution of the Agent Factory pipeline."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class Run(Base, TimestampMixin):
    """A Run tracks one ticket through the pipeline from submission to completion.

    One run = one ticket submission. The run progresses through phases
    (INTAKE → SPEC → ... → DONE), with each phase recorded in the Phase table.
    """

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    ticket_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="INTAKE"
    )
    current_phase: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    total_cost_usd: Mapped[float] = mapped_column(
        Numeric(10, 6), nullable=False, default=0.0
    )
    budget_limit_usd: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    retry_counts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    hitl_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="runs")
    created_by_user: Mapped["User"] = relationship("User", back_populates="runs")
    phases: Mapped[list["Phase"]] = relationship(
        "Phase", back_populates="run", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(
        "Event", back_populates="run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact", back_populates="run", cascade="all, delete-orphan"
    )
    ticket: Mapped[Optional["Ticket"]] = relationship(
        "Ticket", back_populates="run", uselist=False
    )

    def __repr__(self) -> str:
        return (
            f"<Run id={self.id} status={self.status!r} "
            f"phase={self.current_phase!r}>"
        )
