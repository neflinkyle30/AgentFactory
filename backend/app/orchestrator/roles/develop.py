"""Develop role — implements tasks from the design document.

The Develop agent receives the design doc, task list, and repo state
(from previous phases), then implements changes on a clone of the
target repository. It calls the AI provider with role="develop".
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

# ── Develop system prompt ────────────────────────────────────────────

DEVELOP_SYSTEM_PROMPT = """You are a Developer agent. Implement the assigned tasks.
Follow the design document. Respect existing conventions. Run build and lint
after changes. Report any deviations.

## Input Format

You will receive:
1. **Design Document**: The technical design and architecture decisions.
2. **Task List**: Specific implementation tasks to complete.
3. **Repo State**: Current state of the target repository (files, structure).

## Output Format

You MUST respond with valid JSON in this exact structure:
```json
{
  "files_changed": [
    {"path": "<relative file path>", "action": "created|modified|deleted", "description": "<what was done>"}
  ],
  "build_status": {"passed": true, "exit_code": 0, "output": "<build output>"},
  "lint_status": {"passed": true, "exit_code": 0, "output": "<lint output>"},
  "deviations": [
    {"task": "<task id or description>", "reason": "<why it deviated from design>"}
  ],
  "summary": "<brief summary of what was implemented>"
}
```

## Rules
- Read the design document carefully before making changes.
- Follow existing code conventions and patterns in the repository.
- Run build and lint after all changes. Fix any issues before reporting.
- If a task cannot be completed as designed, report it as a deviation with the reason.
- Do NOT modify files outside the declared scope of work.
- Track token usage and report it.
"""


# ── Develop input ────────────────────────────────────────────────────

class DevelopInput:
    """Input data for the Develop phase."""

    def __init__(
        self,
        design_doc: str = "",
        task_list: str = "",
        repo_state: Optional[Dict[str, Any]] = None,
        declared_components: Optional[List[str]] = None,
        workdir: str = "",
    ) -> None:
        self.design_doc = design_doc
        self.task_list = task_list
        self.repo_state = repo_state or {}
        self.declared_components = declared_components or []
        self.workdir = workdir


# ── Develop output ───────────────────────────────────────────────────

class DevelopResult:
    """Structured output from the Develop agent."""

    def __init__(
        self,
        files_changed: Optional[List[Dict[str, str]]] = None,
        build_status: Optional[Dict[str, Any]] = None,
        lint_status: Optional[Dict[str, Any]] = None,
        deviations: Optional[List[Dict[str, str]]] = None,
        summary: str = "",
        raw_response: str = "",
    ) -> None:
        self.files_changed = files_changed or []
        self.build_status = build_status or {"passed": True, "exit_code": 0}
        self.lint_status = lint_status or {"passed": True, "exit_code": 0}
        self.deviations = deviations or []
        self.summary = summary
        self.raw_response = raw_response

    @property
    def build_passed(self) -> bool:
        """True if build succeeded (mock always passes for now)."""
        return self.build_status.get("passed", True)

    @property
    def lint_passed(self) -> bool:
        """True if lint succeeded (mock always passes for now)."""
        return self.lint_status.get("passed", True)

    @property
    def has_changes(self) -> bool:
        """True if at least one file was changed."""
        return len(self.files_changed) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files_changed": self.files_changed,
            "build_status": self.build_status,
            "lint_status": self.lint_status,
            "deviations": self.deviations,
            "summary": self.summary,
        }


# ── Develop Role ─────────────────────────────────────────────────────

class DevelopRole:
    """Executes the Develop phase: implements tasks from the design doc.

    Receives the output of previous phases (design, tasks, specs) and
    calls the AI provider to generate implementation code. Works on a
    clone of the target repository at runs/<id>/workdir.

    Usage:
        role = DevelopRole(provider)
        result = await role.execute(develop_input, db=session)
    """

    def __init__(self, provider: AIProvider) -> None:
        """Initialize the Develop role.

        Args:
            provider: The AI provider to use for code generation.
        """
        self._provider = provider

    async def execute(
        self,
        develop_input: DevelopInput,
        db: Optional[AsyncSession] = None,
    ) -> DevelopResult:
        """Run the Develop agent to implement assigned tasks.

        Args:
            develop_input: The design doc, tasks, repo state, and workdir.
            db: Optional database session for persisting artifacts.

        Returns:
            DevelopResult with files changed, build/lint status, deviations.
        """
        # Build the user message with design doc, task list, and repo state
        user_message = self._build_user_message(develop_input)

        # Call the AI provider
        result = await self._provider.query(
            system_prompt=DEVELOP_SYSTEM_PROMPT,
            messages=[Message(role="user", content=user_message)],
            thinking=True,  # Development benefits from chain-of-thought
            max_tokens=8000,
        )

        # Parse the AI response
        develop_result = self._parse_response(result.content)

        return develop_result

    async def persist_artifact(
        self,
        result: DevelopResult,
        run_id: str,
        db: AsyncSession,
    ) -> Artifact:
        """Persist the develop output as an Artifact in the database.

        Args:
            result: The DevelopResult from execute().
            run_id: The UUID of the parent Run.
            db: Active database session.

        Returns:
            The created Artifact instance.
        """
        artifact = Artifact(
            phase_name="DEVELOP",
            artifact_type="develop_result",
            content_ref=json.dumps(result.to_dict()),
        )
        # Set run_id manually since Artifact doesn't accept it as keyword
        import uuid as _uuid
        artifact.run_id = _uuid.UUID(run_id) if isinstance(run_id, str) else run_id

        db.add(artifact)
        await db.flush()
        return artifact

    # ── Helpers ────────────────────────────────────────────────────

    def _build_user_message(self, develop_input: DevelopInput) -> str:
        """Build the user prompt from design doc, tasks, and repo state."""
        parts = [
            "## Development Request\n",
        ]

        if develop_input.design_doc:
            parts.append("### Design Document")
            parts.append(develop_input.design_doc)
            parts.append("")

        if develop_input.task_list:
            parts.append("### Task List")
            parts.append(develop_input.task_list)
            parts.append("")

        if develop_input.declared_components:
            parts.append("### Declared Components")
            parts.append(", ".join(develop_input.declared_components))
            parts.append("")

        if develop_input.repo_state:
            parts.append("### Repository State")
            parts.append(json.dumps(develop_input.repo_state, indent=2))
            parts.append("")

        parts.append(
            f"### Working Directory\n{develop_input.workdir or 'runs/<id>/workdir'}"
        )
        parts.append("")

        parts.append(
            "\nPlease implement the assigned tasks and return the JSON result "
            "with files changed, build/lint status, and any deviations from the design."
        )
        return "\n".join(parts)

    def _parse_response(self, content: str) -> DevelopResult:
        """Parse the AI response into a DevelopResult.

        Attempts JSON parsing first, falls back to extracting fields
        from the text if the AI didn't return valid JSON.
        """
        try:
            # Try to extract JSON block if present
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
            return DevelopResult(
                files_changed=data.get("files_changed", []),
                build_status=data.get("build_status", {"passed": True, "exit_code": 0}),
                lint_status=data.get("lint_status", {"passed": True, "exit_code": 0}),
                deviations=data.get("deviations", []),
                summary=data.get("summary", ""),
                raw_response=content,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "Failed to parse develop response as JSON: %s. "
                "Falling back to text-based extraction.",
                exc,
            )
            return self._fallback_parse(content)

    def _fallback_parse(self, content: str) -> DevelopResult:
        """Fallback: extract key fields from text when JSON parsing fails.

        Handles the mock provider's text output format.
        """
        import re

        files_changed: List[Dict[str, str]] = []

        # Extract file changes from markdown-style lists
        # Pattern: "- `path/to/file` — description" or "- `path/to/file` (created)"
        file_pattern = r"[-*]\s+`([^`]+)`\s*[-—]\s*(.+?)(?:\n|$)"
        for match in re.finditer(file_pattern, content):
            path = match.group(1).strip()
            desc = match.group(2).strip()
            action = "modified"
            if "created" in desc.lower() or "new" in desc.lower():
                action = "created"
            elif "deleted" in desc.lower() or "removed" in desc.lower():
                action = "deleted"
            files_changed.append({
                "path": path,
                "action": action,
                "description": desc,
            })

        # Extract build/lint status
        build_passed = "build" in content.lower() and "pass" in content.lower()
        lint_passed = "lint" in content.lower() and "pass" in content.lower()

        return DevelopResult(
            files_changed=files_changed,
            build_status={"passed": build_passed, "exit_code": 0 if build_passed else 1},
            lint_status={"passed": lint_passed, "exit_code": 0 if lint_passed else 1},
            deviations=[],
            summary=content[:500],
            raw_response=content,
        )
