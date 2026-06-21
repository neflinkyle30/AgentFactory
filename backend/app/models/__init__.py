"""SQLAlchemy models for Agent Factory.

All models inherit from Base, which provides the shared metadata.
Import all models here so Alembic can detect them via Base.metadata.
"""

from app.models.base import Base
from app.models.team import Team
from app.models.user import User
from app.models.run import Run
from app.models.phase import Phase
from app.models.artifact import Artifact
from app.models.event import Event
from app.models.ticket import Ticket
from app.models.git_credential import GitCredential

__all__ = [
    "Base",
    "Team",
    "User",
    "Run",
    "Phase",
    "Artifact",
    "Event",
    "Ticket",
    "GitCredential",
]
