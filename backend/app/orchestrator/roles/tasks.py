"""Tasks role — breaks the design into atomic implementation tasks.

The Tasks agent reads the design doc and spec requirements, then generates
numbered tasks with dependency info, estimated effort, and requirement
coverage mapping.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AIProvider, Message
from app.models.artifact import Artifact
from app.config import settings

logger = logging.getLogger(__name__)

# ── Tasks system prompt ─────────────────────────────────────────────

TASKS_SYSTEM_PROMPT = """You are the TASK PLANNING AGENT for the Agent Factory pipeline.
Your job is to break a technical design into atomic, ordered implementation tasks.

## Input
You will receive:
1. **Design Document**: The technical design and architecture decisions.
2. **Requirements**: SHALL requirements with GWT scenarios.

## Output Format

You MUST respond with valid JSON in this exact structure:
```json
{
  "tasks": [
    {
      "id": "T-001",
      "description": "Create the User model with SQLAlchemy ORM",
      "dependencies": [],
      "effort": "small",
      "covers_req": ["REQ-001"]
    },
    {
      "id": "T-002",
      "description": "Add JWT auth middleware",
      "dependencies": ["T-001"],
      "effort": "medium",
      "covers_req": ["REQ-001", "REQ-002"]
    }
  ],
  "coverage_pct": 100,
  "total_effort_estimate": "medium"
}
```

## Rules
- Number tasks sequentially as T-001, T-002, etc.
- Each task must have a clear, actionable description.
- Dependencies must reference earlier task IDs (no forward references).
- effort must be one of: "small", "medium", "large".
- covers_req must list which requirement IDs this task addresses.
- Every requirement must be covered by at least one task.
- No circular dependencies allowed.
- coverage_pct must reflect the percentage of requirements that have at least one task.
"""


# ── Tasks input ─────────────────────────────────────────────────────

class TasksInput:
    """Input data for the Tasks phase."""

    def __init__(
        self,
        design_doc: str = "",
        requirements: Optional[List[Dict[str, Any]]] = None,
        spec_output: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.design_doc = design_doc
        self.requirements = requirements or []
        self.spec_output = spec_output or {}


# ── Tasks output ────────────────────────────────────────────────────

class TasksResult:
    """Structured output from the Tasks agent."""

    def __init__(
        self,
        tasks: Optional[List[Dict[str, Any]]] = None,
        coverage_pct: int = 0,
        total_effort_estimate: str = "unknown",
        raw_response: str = "",
    ) -> None:
        self.tasks = tasks or []
        self.coverage_pct = coverage_pct
        self.total_effort_estimate = total_effort_estimate
        self.raw_response = raw_response

    @property
    def passed(self) -> bool:
        """True if coverage_pct == 100 and no circular dependencies."""
        if self.coverage_pct != 100:
            return False
        if self._has_circular_deps():
            return False
        return True

    def _has_circular_deps(self) -> bool:
        """Check for circular dependencies in the task list."""
        # Build adjacency and check for cycles via DFS
        task_ids = {t["id"] for t in self.tasks}
        visited: set = set()
        rec_stack: set = set()

        def dfs(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)
            task = next((t for t in self.tasks if t["id"] == task_id), None)
            if task:
                for dep_id in task.get("dependencies", []):
                    if dep_id not in task_ids:
                        continue  # External dependency — skip
                    if dep_id not in visited:
                        if dfs(dep_id):
                            return True
                    elif dep_id in rec_stack:
                        return True
            rec_stack.discard(task_id)
            return False

        for tid in task_ids:
            if tid not in visited:
                if dfs(tid):
                    return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks": self.tasks,
            "coverage_pct": self.coverage_pct,
            "total_effort_estimate": self.total_effort_estimate,
        }


# ── Tasks Role ──────────────────────────────────────────────────────

class TasksRole:
    """Executes the Tasks phase: breaks design into implementation tasks.

    Reads the design doc and requirements, then generates atomic tasks
    with dependencies, effort estimates, and requirement coverage.
    """

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    async def execute(
        self,
        tasks_input: TasksInput,
        db: Optional[AsyncSession] = None,
    ) -> TasksResult:
        """Run the Tasks agent.

        Args:
            tasks_input: Design doc, requirements, and spec output.
            db: Optional database session.

        Returns:
            TasksResult with task list, coverage, and effort estimate.
        """
        user_message = self._build_user_message(tasks_input)

        result = await self._provider.query(
            system_prompt=TASKS_SYSTEM_PROMPT,
            messages=[Message(role="user", content=user_message)],
            thinking=True,
            max_tokens=6000,
        )

        return self._parse_response(result.content)

    async def persist_artifact(
        self,
        result: TasksResult,
        run_id: str,
        db: AsyncSession,
    ) -> Artifact:
        """Persist the tasks output as an Artifact."""
        import uuid as _uuid

        artifact = Artifact(
            phase_name="TASKS",
            artifact_type="tasks_result",
            content_ref=json.dumps(result.to_dict()),
        )
        artifact.run_id = _uuid.UUID(run_id) if isinstance(run_id, str) else run_id
        db.add(artifact)
        await db.flush()
        return artifact

    # ── Helpers ────────────────────────────────────────────────────

    def _build_user_message(self, tasks_input: TasksInput) -> str:
        parts = [
            "## Task Planning Request\n",
        ]

        if tasks_input.design_doc:
            parts.append("### Design Document")
            parts.append(tasks_input.design_doc)
            parts.append("")

        if tasks_input.requirements:
            parts.append("### Requirements")
            for req in tasks_input.requirements:
                req_id = req.get("id", "?")
                shall = req.get("shall_text", "")
                parts.append(f"- **{req_id}**: {shall}")
            parts.append("")

        if tasks_input.spec_output:
            parts.append("### Spec Output")
            parts.append(json.dumps(tasks_input.spec_output, indent=2))
            parts.append("")

        parts.append(
            "\nPlease break the design into atomic implementation tasks "
            "with dependencies, effort estimates, and requirement coverage. "
            "Return the JSON result."
        )
        return "\n".join(parts)

    def _parse_response(self, content: str) -> TasksResult:
        try:
            json_str = content
            if "```json" in content:
                start = content.index("```json") + 7
                end = content.index("```", start)
                json_str = content[start:end].strip()
            elif "```" in content:
                start = content.index("```") + 3
                end = content.index("```", start)
                json_str = content[start:end].strip()

            data = json.loads(json_str)
            return TasksResult(
                tasks=data.get("tasks", []),
                coverage_pct=int(data.get("coverage_pct", 0)),
                total_effort_estimate=data.get("total_effort_estimate", "unknown"),
                raw_response=content,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "Failed to parse tasks response as JSON: %s. Returning empty result.",
                exc,
            )
            return TasksResult(
                tasks=[],
                coverage_pct=0,
                raw_response=content,
            )
