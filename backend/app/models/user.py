"""User model — authentication and team membership."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class User(Base, TimestampMixin):
    """A user belongs to a team and has a role for authorization."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="developer"
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="users")
    runs: Mapped[list["Run"]] = relationship("Run", back_populates="created_by_user")
    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket", back_populates="created_by_user"
    )
    git_credentials: Mapped[list["GitCredential"]] = relationship(
        "GitCredential", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"
