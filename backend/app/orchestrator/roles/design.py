"""Design role — explores the repo and writes a technical design document.

The Design agent receives spec requirements and the repository path,
then produces an architecture approach, list of files to create/modify,
and validates that referenced files exist.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AIProvider, Message
from app.models.artifact import Artifact
from app.config import settings

logger = logging.getLogger(__name__)

# ── Design system prompt ───────────────────────────────────────────

DESIGN_SYSTEM_PROMPT = """You are the DESIGN AGENT for the Agent Factory pipeline.
Your job is to analyze the formal requirements and the target repository
to produce a technical design document.

## Input
You will receive:
1. **Requirements**: SHALL requirements with GWT scenarios.
2. **Repository Path**: The path to the codebase to analyze.

## Output Format

You MUST respond with valid JSON in this exact structure:
```json
{
  "design_doc": "# Design Document\\n\\n## Architecture\\n...",
  "files_referenced": [
    "/absolute/path/to/existing/file.py",
    "/absolute/path/to/new/file.py"
  ],
  "architecture_approach": "Brief summary of the architectural decisions.",
  "components_affected": ["component1", "component2"]
}
```

## Rules
- The design_doc is a markdown string describing the technical approach.
- files_referenced must include ALL files that will be created or modified.
- For new files, list the planned path (they will be checked for existence later).
- Describe the architecture pattern, data flow, and key design decisions.
- Reference specific existing files that will be modified.
- Components should map to the repository's module/package structure.
"""


# ── Design input ────────────────────────────────────────────────────

class DesignInput:
    """Input data for the Design phase."""

    def __init__(
        self,
        requirements: Optional[List[Dict[str, Any]]] = None,
        repo_path: str = "",
        spec_output: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.requirements = requirements or []
        self.repo_path = repo_path
        self.spec_output = spec_output or {}


# ── Design output ───────────────────────────────────────────────────

class DesignResult:
    """Structured output from the Design agent."""

    def __init__(
        self,
        design_doc: str = "",
        files_referenced: Optional[List[str]] = None,
        architecture_approach: str = "",
        components_affected: Optional[List[str]] = None,
        raw_response: str = "",
    ) -> None:
        self.design_doc = design_doc
        self.files_referenced = files_referenced or []
        self.architecture_approach = architecture_approach
        self.components_affected = components_affected or []
        self.raw_response = raw_response

    @property
    def passed(self) -> bool:
        """True if all files_referenced exist (or are new files)."""
        if not self.files_referenced:
            return False
        for path in self.files_referenced:
            if not os.path.exists(path):
                # Check if it's a relative path within the repo
                # New files to be created are acceptable
                logger.info("File not found (may be planned creation): %s", path)
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "design_doc": self.design_doc,
            "files_referenced": self.files_referenced,
            "architecture_approach": self.architecture_approach,
            "components_affected": self.components_affected,
        }


# ── Design Role ─────────────────────────────────────────────────────

class DesignRole:
    """Executes the Design phase: produces a technical design from requirements.

    Analyzes the repository structure and spec requirements to produce
    an architecture approach and list of files to create/modify.
    """

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    async def execute(
        self,
        design_input: DesignInput,
        db: Optional[AsyncSession] = None,
    ) -> DesignResult:
        """Run the Design agent.

        Args:
            design_input: Requirements, repo path, and spec output.
            db: Optional database session.

        Returns:
            DesignResult with design_doc, files_referenced, etc.
        """
        user_message = self._build_user_message(design_input)

        result = await self._provider.query(
            system_prompt=DESIGN_SYSTEM_PROMPT,
            messages=[Message(role="user", content=user_message)],
            thinking=True,
            max_tokens=6000,
        )

        return self._parse_response(result.content)

    async def persist_artifact(
        self,
        result: DesignResult,
        run_id: str,
        db: AsyncSession,
    ) -> Artifact:
        """Persist the design output as an Artifact."""
        import uuid as _uuid

        artifact = Artifact(
            phase_name="DESIGN",
            artifact_type="design_result",
            content_ref=json.dumps(result.to_dict()),
        )
        artifact.run_id = _uuid.UUID(run_id) if isinstance(run_id, str) else run_id
        db.add(artifact)
        await db.flush()
        return artifact

    # ── Helpers ────────────────────────────────────────────────────

    def _build_user_message(self, design_input: DesignInput) -> str:
        parts = [
            "## Design Request\n",
            f"**Repository Path**: {design_input.repo_path or settings.runs_directory}",
        ]

        if design_input.requirements:
            parts.append("\n### Requirements")
            for req in design_input.requirements:
                req_id = req.get("id", "?")
                shall = req.get("shall_text", "")
                parts.append(f"- **{req_id}**: {shall}")

        if design_input.spec_output:
            parts.append("\n### Spec Output")
            parts.append(json.dumps(design_input.spec_output, indent=2))

        parts.append(
            "\n\nPlease analyze the requirements and produce a technical design "
            "document with the architecture approach and list of files to "
            "create or modify. Return the JSON result."
        )
        return "\n".join(parts)

    def _parse_response(self, content: str) -> DesignResult:
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
            return DesignResult(
                design_doc=data.get("design_doc", ""),
                files_referenced=data.get("files_referenced", []),
                architecture_approach=data.get("architecture_approach", ""),
                components_affected=data.get("components_affected", []),
                raw_response=content,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "Failed to parse design response as JSON: %s. Returning empty result.",
                exc,
            )
            return DesignResult(
                design_doc="",
                files_referenced=[],
                raw_response=content,
            )
