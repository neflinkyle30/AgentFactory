"""Phase model — records each pipeline phase execution within a run."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Phase(Base):
    """One row per phase per run. Records the outcome of each pipeline stage.

    Composite primary key: (run_id, phase_name).
    """

    __tablename__ = "phases"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    phase_name: Mapped[str] = mapped_column(
        String(30), primary_key=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="phases")

    def __repr__(self) -> str:
        return (
            f"<Phase run_id={self.run_id} phase={self.phase_name!r} "
            f"status={self.status!r}>"
        )
