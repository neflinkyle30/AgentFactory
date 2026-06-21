"""GitCredential model — per-user Git provider authentication tokens."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid


class GitCredential(Base):
    """Stores encrypted Git provider credentials per user.

    Tokens are encrypted at rest (Fernet) and decrypted at runtime.
    Each user can have credentials for multiple providers.
    """

    __tablename__ = "git_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    token: Mapped[str] = mapped_column(Text, nullable=False)
    remote_url: Mapped[str] = mapped_column(String(2000), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="git_credentials")

    def __repr__(self) -> str:
        return (
            f"<GitCredential id={self.id} user_id={self.user_id} "
            f"provider={self.provider!r}>"
        )
