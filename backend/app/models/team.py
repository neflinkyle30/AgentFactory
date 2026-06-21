"""Team model — top-level multi-tenancy boundary."""

import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class Team(Base, TimestampMixin):
    """A team is the top-level isolation boundary. All resources are scoped to a team."""

    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="team")
    runs: Mapped[list["Run"]] = relationship("Run", back_populates="team")

    def __repr__(self) -> str:
        return f"<Team id={self.id} name={self.name!r}>"
