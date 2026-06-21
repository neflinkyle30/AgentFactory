"""Ticket model — normalized intake output from the Intake agent."""

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid


class Ticket(Base):
    """The normalized ticket produced by the Intake agent after validation.

    Linked to a Run. Contains the structured fields extracted from the
    raw ticket submission (Jira or form-based).
    """

    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id"),
        nullable=True,
        unique=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    components: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    raw_ticket: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    completeness_score: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # Relationships
    run: Mapped[Optional["Run"]] = relationship("Run", back_populates="ticket")
    created_by_user: Mapped["User"] = relationship(
        "User", back_populates="tickets"
    )

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} title={self.title!r} score={self.completeness_score}>"
