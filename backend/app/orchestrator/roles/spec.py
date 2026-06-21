"""Spec role — reads the intake-normalized ticket and writes formal requirements.

The Spec agent generates SHALL requirements with Given-When-Then scenarios
and validates that all acceptance criteria are covered.
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

# ── Spec system prompt ─────────────────────────────────────────────

SPEC_SYSTEM_PROMPT = """You are the SPECIFICATION AGENT for the Agent Factory pipeline.
Your job is to read the intake-normalized ticket and produce formal software requirements.

## Input
You will receive a normalized ticket with:
- Title
- Description
- Acceptance Criteria (Given-When-Then format)

## Output Format

You MUST respond with valid JSON in this exact structure:
```json
{
  "requirements": [
    {
      "id": "REQ-001",
      "shall_text": "The system SHALL ...",
      "gwt": {
        "given": "precondition context",
        "when": "action or event",
        "then": "expected outcome"
      }
    }
  ],
  "coverage_pct": 100,
  "schema_version": "1.0"
}
```

## Rules
- Number requirements sequentially as REQ-001, REQ-002, etc.
- Each SHALL statement must be precise, testable, and unambiguous.
- Each acceptance criterion must map to at least one requirement.
- coverage_pct must be 100 (all ACs covered) — if any AC has no corresponding requirement, set coverage_pct to less than 100.
- Write SHALL requirements in the format: "The system SHALL <behavior>".
- GWT scenarios must be concrete and testable.
- Identify any missing or ambiguous ACs in a "gaps" field if coverage < 100.
"""


# ── Spec input ──────────────────────────────────────────────────────

class SpecInput:
    """Input data for the Spec phase."""

    def __init__(
        self,
        title: str = "",
        description: str = "",
        acceptance_criteria: Optional[List[Dict[str, str]]] = None,
        normalized_ticket: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.title = title
        self.description = description
        self.acceptance_criteria = acceptance_criteria or []
        self.normalized_ticket = normalized_ticket or {}


# ── Spec output ─────────────────────────────────────────────────────

class SpecResult:
    """Structured output from the Spec agent."""

    def __init__(
        self,
        requirements: Optional[List[Dict[str, Any]]] = None,
        coverage_pct: int = 0,
        schema_version: str = "1.0",
        gaps: Optional[List[str]] = None,
        raw_response: str = "",
    ) -> None:
        self.requirements = requirements or []
        self.coverage_pct = coverage_pct
        self.schema_version = schema_version
        self.gaps = gaps or []
        self.raw_response = raw_response

    @property
    def passed(self) -> bool:
        """True if all ACs are covered (coverage_pct == 100)."""
        return self.coverage_pct == 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirements": self.requirements,
            "coverage_pct": self.coverage_pct,
            "schema_version": self.schema_version,
            "gaps": self.gaps,
        }


# ── Spec Role ───────────────────────────────────────────────────────

class SpecRole:
    """Executes the Spec phase: generates formal requirements from the ticket.

    Uses the configured AI provider to produce SHALL requirements and
    Given-When-Then scenarios for each acceptance criterion.
    """

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    async def execute(
        self,
        spec_input: SpecInput,
        db: Optional[AsyncSession] = None,
    ) -> SpecResult:
        """Run the Spec agent against a normalized ticket.

        Args:
            spec_input: The normalized ticket data.
            db: Optional database session.

        Returns:
            SpecResult with requirements, coverage_pct, and gaps.
        """
        user_message = self._build_user_message(spec_input)

        result = await self._provider.query(
            system_prompt=SPEC_SYSTEM_PROMPT,
            messages=[Message(role="user", content=user_message)],
            thinking=True,
            max_tokens=4000,
        )

        return self._parse_response(result.content)

    async def persist_artifact(
        self,
        result: SpecResult,
        run_id: str,
        db: AsyncSession,
    ) -> Artifact:
        """Persist the spec output as an Artifact."""
        import uuid as _uuid

        artifact = Artifact(
            phase_name="SPEC",
            artifact_type="spec_result",
            content_ref=json.dumps(result.to_dict()),
        )
        artifact.run_id = _uuid.UUID(run_id) if isinstance(run_id, str) else run_id
        db.add(artifact)
        await db.flush()
        return artifact

    # ── Helpers ────────────────────────────────────────────────────

    def _build_user_message(self, spec_input: SpecInput) -> str:
        parts = [
            "## Specification Request\n",
            f"**Title**: {spec_input.title}",
            f"**Description**: {spec_input.description}",
        ]

        if spec_input.normalized_ticket:
            parts.append("\n### Normalized Ticket")
            parts.append(json.dumps(spec_input.normalized_ticket, indent=2))

        if spec_input.acceptance_criteria:
            parts.append("\n### Acceptance Criteria")
            for i, ac in enumerate(spec_input.acceptance_criteria, 1):
                if isinstance(ac, dict):
                    parts.append(
                        f"{i}. Given {ac.get('given', '?')}, "
                        f"When {ac.get('when', '?')}, "
                        f"Then {ac.get('then', '?')}"
                    )
                else:
                    parts.append(f"{i}. {ac}")

        parts.append(
            "\n\nPlease generate formal SHALL requirements with GWT scenarios "
            "for each acceptance criterion. Return the JSON result."
        )
        return "\n".join(parts)

    def _parse_response(self, content: str) -> SpecResult:
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
            return SpecResult(
                requirements=data.get("requirements", []),
                coverage_pct=int(data.get("coverage_pct", 0)),
                schema_version=data.get("schema_version", "1.0"),
                gaps=data.get("gaps", []),
                raw_response=content,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "Failed to parse spec response as JSON: %s. Returning empty result.",
                exc,
            )
            return SpecResult(
                requirements=[],
                coverage_pct=0,
                gaps=[],
                raw_response=content,
            )
