"""Intake role — validates and normalizes incoming tickets.

The Intake agent evaluates a ticket against a completeness rubric (0-100),
normalizes the ticket into a canonical JSON structure, and determines
whether the ticket passes G1 (score ≥ 80) or bounces back.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AIProvider, Message
from app.models.artifact import Artifact
from app.models.ticket import Ticket
from app.config import settings

logger = logging.getLogger(__name__)

# ── Intake system prompt ────────────────────────────────────────────

INTAKE_SYSTEM_PROMPT = """You are the INTAKE AGENT for the Agent Factory pipeline.
Your job is to evaluate an incoming ticket, compute a completeness score (0-100),
normalize the ticket into canonical JSON, and identify missing or insufficient fields.

## Rubric (0-100 points total)

- **Acceptance Criteria presence and quality** (40 pts): Are there GIVEN-WHEN-THEN
  acceptance criteria? Are they specific and testable? Vague ACs (e.g. "it should work")
  score low. Missing ACs score 0.
- **Description clarity** (25 pts): Is the problem clearly described? Does it explain
  what needs to change and why? Ambiguous descriptions score lower.
- **Title specificity** (15 pts): Is the title descriptive, searchable, and specific?
  Generic titles ("fix bug") score low.
- **Priority and sizing** (10 pts): Is a priority assigned? Is effort estimated?
- **Component identification** (10 pts): Are the affected components/modules listed?

## Output Format

You MUST respond with valid JSON in this exact structure:
```json
{
  "completeness_score": <int 0-100>,
  "rubric_breakdown": {
    "ac_quality": <int 0-40>,
    "description_clarity": <int 0-25>,
    "title_specificity": <int 0-15>,
    "priority_sizing": <int 0-10>,
    "component_identification": <int 0-10>
  },
  "missing": [<list of field names that are missing or insufficient>],
  "suggestions": [<list of actionable suggestions for improvement>],
  "normalized_ticket": {
    "normalized_title": "<clear, specific title>",
    "normalized_description": "<refined description>",
    "acceptance_criteria": [
      {"given": "<context>", "when": "<action>", "then": "<expected outcome>"}
    ],
    "priority": "<priority level>",
    "components": ["<component1>", "<component2>"]
  }
}
```

## Rules
- Score honestly based on the rubric. Do NOT inflate scores.
- If score < 80, the run will BOUNCE — provide actionable suggestions.
- Normalize the title: make it specific and searchable.
- Extract or infer acceptance criteria in Given-When-Then format.
- Components should be specific module/package names.
"""


# ── Ticket input schema ─────────────────────────────────────────────
# What the API receives and passes to the intake agent.

class TicketInput:
    """Raw ticket data before intake processing."""

    def __init__(
        self,
        title: str,
        description: str = "",
        acceptance_criteria: Optional[List[Dict[str, str]]] = None,
        priority: str = "medium",
        components: Optional[List[str]] = None,
        ticket_source: str = "form",
        ticket_key: Optional[str] = None,
        raw_ticket: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.title = title
        self.description = description
        self.acceptance_criteria = acceptance_criteria or []
        self.priority = priority
        self.components = components or []
        self.ticket_source = ticket_source
        self.ticket_key = ticket_key
        self.raw_ticket = raw_ticket or {}


# ── Intake output ───────────────────────────────────────────────────

class IntakeResult:
    """Structured output from the Intake agent."""

    def __init__(
        self,
        completeness_score: int,
        missing: List[str],
        suggestions: List[str],
        normalized_ticket: Dict[str, Any],
        rubric_breakdown: Optional[Dict[str, int]] = None,
        raw_response: str = "",
    ) -> None:
        self.completeness_score = completeness_score
        self.missing = missing
        self.suggestions = suggestions
        self.normalized_ticket = normalized_ticket
        self.rubric_breakdown = rubric_breakdown or {}
        self.raw_response = raw_response

    @property
    def passed(self) -> bool:
        """True if the ticket scored ≥ 80 and passes G1."""
        return self.completeness_score >= 80

    def to_dict(self) -> Dict[str, Any]:
        return {
            "completeness_score": self.completeness_score,
            "missing": self.missing,
            "suggestions": self.suggestions,
            "normalized_ticket": self.normalized_ticket,
            "rubric_breakdown": self.rubric_breakdown,
        }


# ── Intake Role ─────────────────────────────────────────────────────

class IntakeRole:
    """Executes the Intake phase: validates, scores, and normalizes a ticket.

    Uses the configured AI provider to analyze the ticket against the
    completeness rubric, then persists the result as a Ticket + Artifact
    in the database.
    """

    def __init__(self, provider: AIProvider) -> None:
        """Initialize the Intake role.

        Args:
            provider: The AI provider to use for intake analysis.
        """
        self._provider = provider

    async def evaluate(
        self,
        ticket_input: TicketInput,
        db: Optional[AsyncSession] = None,
    ) -> IntakeResult:
        """Run the Intake agent against a ticket submission.

        Args:
            ticket_input: The raw ticket data from the API.
            db: Optional database session for persisting artifacts.

        Returns:
            IntakeResult with score, missing fields, suggestions, and
            the normalized ticket.
        """
        # Build the user message with the raw ticket
        user_message = self._build_user_message(ticket_input)

        # Call the AI provider
        result = await self._provider.query(
            system_prompt=INTAKE_SYSTEM_PROMPT,
            messages=[Message(role="user", content=user_message)],
            thinking=False,  # Intake is straightforward — no CoT needed
            max_tokens=2000,
        )

        # Parse the AI response
        intake_result = self._parse_response(result.content)

        # Persist to database if session is provided
        if db is not None and ticket_input.ticket_key is None:
            # Only auto-save for form-based tickets (not Jira imports)
            pass  # Persistence is handled by the orchestrator

        return intake_result

    async def persist_ticket(
        self,
        result: IntakeResult,
        run_id: str,
        created_by: str,
        raw_ticket: Dict[str, Any],
        db: AsyncSession,
    ) -> Ticket:
        """Create a Ticket and Artifact row in the database.

        Args:
            result: The IntakeResult from evaluate().
            run_id: The UUID of the parent Run.
            created_by: The UUID of the user who submitted.
            raw_ticket: The original ticket payload.
            db: Active database session.

        Returns:
            The created Ticket instance.
        """
        import uuid as _uuid

        ticket = Ticket(
            id=_uuid.UUID(run_id) if isinstance(run_id, str) else run_id,
            run_id=_uuid.UUID(run_id) if isinstance(run_id, str) else run_id,
            title=result.normalized_ticket.get("normalized_title", ""),
            description=result.normalized_ticket.get("normalized_description", ""),
            acceptance_criteria=result.normalized_ticket.get("acceptance_criteria"),
            components=result.normalized_ticket.get("components"),
            priority=result.normalized_ticket.get("priority", "medium"),
            created_by=_uuid.UUID(created_by) if isinstance(created_by, str) else created_by,
            raw_ticket=raw_ticket,
            completeness_score=result.completeness_score,
        )

        db.add(ticket)

        # Also create an Artifact for the intake output
        artifact = Artifact(
            run_id=ticket.run_id,
            phase_name="INTAKE",
            artifact_type="intake_result",
            content_ref=json.dumps(result.to_dict()),
        )
        db.add(artifact)

        await db.flush()
        return ticket

    # ── Helpers ────────────────────────────────────────────────────

    def _build_user_message(self, ticket_input: TicketInput) -> str:
        """Build the user prompt from the raw ticket."""
        parts = [
            "## Ticket Submission\n",
            f"**Title**: {ticket_input.title}",
            f"**Description**: {ticket_input.description}",
            f"**Priority**: {ticket_input.priority}",
            f"**Components**: {', '.join(ticket_input.components) if ticket_input.components else 'none specified'}",
            f"**Source**: {ticket_input.ticket_source}",
        ]

        if ticket_input.ticket_key:
            parts.append(f"**Ticket Key**: {ticket_input.ticket_key}")

        if ticket_input.acceptance_criteria:
            parts.append("\n### Acceptance Criteria")
            for i, ac in enumerate(ticket_input.acceptance_criteria, 1):
                if isinstance(ac, dict):
                    parts.append(
                        f"{i}. Given {ac.get('given', '?')}, "
                        f"When {ac.get('when', '?')}, "
                        f"Then {ac.get('then', '?')}"
                    )
                else:
                    parts.append(f"{i}. {ac}")

        parts.append(
            "\n\nPlease evaluate this ticket and return the JSON result."
        )
        return "\n".join(parts)

    def _parse_response(self, content: str) -> IntakeResult:
        """Parse the AI response into an IntakeResult.

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
            return IntakeResult(
                completeness_score=int(data.get("completeness_score", 0)),
                missing=data.get("missing", []),
                suggestions=data.get("suggestions", []),
                normalized_ticket=data.get("normalized_ticket", {}),
                rubric_breakdown=data.get("rubric_breakdown", {}),
                raw_response=content,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "Failed to parse intake response as JSON: %s. "
                "Falling back to rubric-based scoring from text.",
                exc,
            )
            return self._fallback_parse(content)

    def _fallback_parse(self, content: str) -> IntakeResult:
        """Fallback: extract completeness score from text when JSON parsing fails.

        Scans for patterns like 'Completeness Score: 85/100' or 'score: 92'.
        This handles the mock provider's text output format.
        """
        import re

        # Try to find score in the text
        score = 0
        patterns = [
            r"[Cc]ompleteness\s*[Ss]core\s*:\s*(\d+)\s*/\s*100",
            r"[Ss]core\s*:\s*(\d+)",
            r"(\d+)\s*/\s*100",
        ]
        for pat in patterns:
            match = re.search(pat, content)
            if match:
                score = int(match.group(1))
                break

        # Determine missing/suggestions from keywords
        missing: List[str] = []
        suggestions: List[str] = []

        if score < 80:
            # Infer missing fields from the content
            if "acceptance criteria" in content.lower() and "missing" in content.lower():
                missing.append("acceptance_criteria")
            if "description" in content.lower() and "vague" in content.lower():
                missing.append("description")

        return IntakeResult(
            completeness_score=score,
            missing=missing,
            suggestions=suggestions,
            normalized_ticket={},
            raw_response=content,
        )


# ── Deterministic scorer (no AI needed) ────────────────────────────
# Used as a fallback or for deterministic testing without an LLM call.


def score_ticket_deterministic(ticket_input: TicketInput) -> IntakeResult:
    """Score a ticket using simple heuristics — no AI call.

    This is a lightweight fallback for testing or when the AI provider
    is not available. Uses the same rubric as the AI-based intake.

    Returns:
        IntakeResult with a deterministic score and suggestions.
    """
    score = 0
    missing: List[str] = []
    suggestions: List[str] = []

    # AC quality (40 pts)
    acs = ticket_input.acceptance_criteria
    if not acs:
        missing.append("acceptance_criteria")
        suggestions.append("Write at least 1 acceptance criterion in Given-When-Then format")
    else:
        # Score based on number and quality of ACs
        ac_score = min(len(acs) * 15, 40)
        for ac in acs:
            if isinstance(ac, dict):
                has_all = all(k in ac for k in ("given", "when", "then"))
                if not has_all:
                    ac_score = max(ac_score - 10, 0)
            else:
                ac_score = max(ac_score - 10, 0)
        score += ac_score

    # Description clarity (25 pts)
    desc = ticket_input.description.strip()
    if not desc:
        missing.append("description")
        suggestions.append("Add a clear description of the problem and desired outcome")
    else:
        word_count = len(desc.split())
        if word_count < 5:
            score += 5
            suggestions.append("Expand the description with more detail")
        elif word_count < 20:
            score += 15
        else:
            score += 25

    # Title specificity (15 pts)
    title = ticket_input.title.strip()
    if not title:
        missing.append("title")
        suggestions.append("Provide a specific, searchable title")
    else:
        word_count = len(title.split())
        if word_count < 2:
            score += 3
        elif word_count < 5:
            score += 10
        else:
            score += 15

    # Priority (10 pts)
    priority = ticket_input.priority.lower()
    if priority in ("critical", "high", "medium", "low"):
        score += 10
    else:
        score += 5
        suggestions.append("Set a valid priority: critical, high, medium, or low")

    # Components (10 pts)
    if ticket_input.components:
        score += min(len(ticket_input.components) * 5, 10)
    else:
        missing.append("components")
        suggestions.append("List the affected components or modules")

    # Build normalized ticket
    normalized = {
        "normalized_title": ticket_input.title,
        "normalized_description": ticket_input.description,
        "acceptance_criteria": ticket_input.acceptance_criteria,
        "priority": ticket_input.priority,
        "components": ticket_input.components,
    }

    return IntakeResult(
        completeness_score=min(score, 100),
        missing=missing,
        suggestions=suggestions,
        normalized_ticket=normalized,
    )
