"""Artifact model — immutable records of pipeline outputs.

Artifacts link to files in runs/<run_id>/ or store inline text content.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid, utcnow


class Artifact(Base):
    """An immutable artifact produced by a pipeline phase.

    Artifacts are stored either as file references (content_ref points to
    a path under runs/<run_id>/) or as inline text content.
    """

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phase_name: Mapped[str] = mapped_column(String(30), nullable=False)
    artifact_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    content_ref: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="artifacts")

    def __repr__(self) -> str:
        return (
            f"<Artifact id={self.id} type={self.artifact_type!r} "
            f"phase={self.phase_name!r}>"
        )
