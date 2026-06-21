"""Role implementations — one module per pipeline phase."""

from app.orchestrator.roles.intake import IntakeRole, TicketInput, IntakeResult
from app.orchestrator.roles.spec import SpecRole, SpecInput, SpecResult
from app.orchestrator.roles.design import DesignRole, DesignInput, DesignResult
from app.orchestrator.roles.tasks import TasksRole, TasksInput, TasksResult
from app.orchestrator.roles.develop import DevelopRole, DevelopInput, DevelopResult
from app.orchestrator.roles.verify import VerifyRole, VerifyInput, VerifyResult
from app.orchestrator.roles.review import ReviewRole, ReviewInput, ReviewResult
from app.orchestrator.roles.pr_agent import PRAgentRole, PRAgentInput, PRAgentResult

__all__ = [
    "IntakeRole", "TicketInput", "IntakeResult",
    "SpecRole", "SpecInput", "SpecResult",
    "DesignRole", "DesignInput", "DesignResult",
    "TasksRole", "TasksInput", "TasksResult",
    "DevelopRole", "DevelopInput", "DevelopResult",
    "VerifyRole", "VerifyInput", "VerifyResult",
    "ReviewRole", "ReviewInput", "ReviewResult",
    "PRAgentRole", "PRAgentInput", "PRAgentResult",
]
