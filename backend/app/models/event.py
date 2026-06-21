"""Event model — immutable audit trail for a run.

Events record every state change, gate evaluation, retry, and error.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Event(Base):
    """Append-only audit trail entry for a run.

    Each event is sequenced per run and records the type, payload,
    and timestamp of every significant pipeline occurrence.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="events")

    def __repr__(self) -> str:
        return (
            f"<Event id={self.id} run_id={self.run_id} "
            f"seq={self.seq} type={self.event_type!r}>"
        )
