"""Review role — performs a read-only 5-dimension review.

The Review agent analyzes the diff, design doc, and spec across five
dimensions: Security, Integrity, Performance, Architecture, Quality.
Each finding gets a severity rating.
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

# ── Review system prompt ────────────────────────────────────────────

REVIEW_SYSTEM_PROMPT = """You are the REVIEW AGENT for the Agent Factory pipeline.
Your job is to perform a read-only, 5-dimension review of the implementation.

## Dimensions
1. **Security**: Auth, secrets, injections, input validation, data exposure.
2. **Integrity**: Data consistency, error handling, transactions, idempotency.
3. **Performance**: N+1 queries, memory leaks, algorithmic complexity, caching.
4. **Architecture**: Design pattern adherence, SOLID, coupling, cohesion.
5. **Quality**: Readability, naming, tests, documentation, conventions.

## Severity Levels
- **CRITICAL**: Must fix before merge (security hole, data corruption, etc.)
- **WARNING**: Should fix (performance issue, code smell, design deviation)
- **SUGGESTION**: Nice to have (style improvement, optional optimization)
- **OK**: No issues found in this dimension

## Output Format

You MUST respond with valid JSON in this exact structure:
```json
{
  "verdict": "APPROVED",
  "findings": [
    {
      "dimension": "Security",
      "severity": "CRITICAL",
      "description": "API key hardcoded in config.py line 42",
      "file": "app/config.py",
      "line": 42
    }
  ],
  "summary": "1 critical finding, 2 warnings. Recommended fixes before merge.",
  "dimension_summary": {
    "Security": "WARNING",
    "Integrity": "OK",
    "Performance": "SUGGESTION",
    "Architecture": "OK",
    "Quality": "WARNING"
  }
}
```

## Rules
- Verdict must be: APPROVED, APPROVED_WITH_SUGGESTIONS, or REJECTED.
- REJECTED requires at least one CRITICAL finding.
- APPROVED_WITH_SUGGESTIONS requires at least one WARNING or SUGGESTION (but no CRITICAL).
- APPROVED means no findings above SUGGESTION level.
- Each finding must include dimension, severity, description, file, and line.
- Review is READ-ONLY — do not modify any files.
- Focus on actionable findings, not theoretical risks.
"""


# ── Review input ────────────────────────────────────────────────────

class ReviewInput:
    """Input data for the Review phase."""

    def __init__(
        self,
        diff_content: str = "",
        design_doc: str = "",
        requirements: Optional[List[Dict[str, Any]]] = None,
        files_changed: Optional[List[Dict[str, str]]] = None,
        spec_output: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.diff_content = diff_content
        self.design_doc = design_doc
        self.requirements = requirements or []
        self.files_changed = files_changed or []
        self.spec_output = spec_output or {}


# ── Review output ───────────────────────────────────────────────────

class ReviewResult:
    """Structured output from the Review agent."""

    VALID_VERDICTS = {"APPROVED", "APPROVED_WITH_SUGGESTIONS", "REJECTED"}

    def __init__(
        self,
        verdict: str = "APPROVED",
        findings: Optional[List[Dict[str, Any]]] = None,
        summary: str = "",
        dimension_summary: Optional[Dict[str, str]] = None,
        raw_response: str = "",
    ) -> None:
        self.verdict = verdict
        self.findings = findings or []
        self.summary = summary
        self.dimension_summary = dimension_summary or {}
        self.raw_response = raw_response

    @property
    def passed(self) -> bool:
        """True if verdict is APPROVED or APPROVED_WITH_SUGGESTIONS and no CRITICAL findings."""
        if self.verdict not in self.VALID_VERDICTS:
            return False
        if self.verdict == "REJECTED":
            return False
        has_critical = any(
            f.get("severity") == "CRITICAL" for f in self.findings
        )
        return not has_critical

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "findings": self.findings,
            "summary": self.summary,
            "dimension_summary": self.dimension_summary,
        }


# ── Review Role ─────────────────────────────────────────────────────

class ReviewRole:
    """Executes the Review phase: 5-dimension review of the implementation.

    Analyzes the diff, design doc, and spec for security, integrity,
    performance, architecture, and quality issues.
    """

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    async def execute(
        self,
        review_input: ReviewInput,
        db: Optional[AsyncSession] = None,
    ) -> ReviewResult:
        """Run the Review agent.

        Args:
            review_input: Diff, design doc, spec, and files changed.
            db: Optional database session.

        Returns:
            ReviewResult with verdict, findings, and dimension summary.
        """
        user_message = self._build_user_message(review_input)

        result = await self._provider.query(
            system_prompt=REVIEW_SYSTEM_PROMPT,
            messages=[Message(role="user", content=user_message)],
            thinking=True,
            max_tokens=6000,
        )

        return self._parse_response(result.content)

    async def persist_artifact(
        self,
        result: ReviewResult,
        run_id: str,
        db: AsyncSession,
    ) -> Artifact:
        """Persist the review output as an Artifact."""
        import uuid as _uuid

        artifact = Artifact(
            phase_name="REVIEW",
            artifact_type="review_result",
            content_ref=json.dumps(result.to_dict()),
        )
        artifact.run_id = _uuid.UUID(run_id) if isinstance(run_id, str) else run_id
        db.add(artifact)
        await db.flush()
        return artifact

    # ── Helpers ────────────────────────────────────────────────────

    def _build_user_message(self, review_input: ReviewInput) -> str:
        parts = [
            "## Review Request\n",
        ]

        if review_input.design_doc:
            parts.append("### Design Document")
            parts.append(review_input.design_doc[:3000])
            parts.append("")

        if review_input.diff_content:
            parts.append("### Diff Content")
            # Truncate diff to avoid overwhelming context
            diff_snippet = review_input.diff_content[:5000]
            parts.append(f"```diff\n{diff_snippet}\n```")
            parts.append("")

        if review_input.files_changed:
            parts.append("### Files Changed")
            for f in review_input.files_changed:
                parts.append(
                    f"- `{f.get('path', '?')}` ({f.get('action', 'modified')})"
                )
            parts.append("")

        if review_input.requirements:
            parts.append("### Requirements")
            for req in review_input.requirements:
                req_id = req.get("id", "?")
                shall = req.get("shall_text", "")
                parts.append(f"- **{req_id}**: {shall}")
            parts.append("")

        parts.append(
            "\nPlease review the implementation across all 5 dimensions "
            "(Security, Integrity, Performance, Architecture, Quality). "
            "Return the JSON result with verdict and findings."
        )
        return "\n".join(parts)

    def _parse_response(self, content: str) -> ReviewResult:
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
            return ReviewResult(
                verdict=data.get("verdict", "APPROVED"),
                findings=data.get("findings", []),
                summary=data.get("summary", ""),
                dimension_summary=data.get("dimension_summary", {}),
                raw_response=content,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "Failed to parse review response as JSON: %s. Returning default.",
                exc,
            )
            return ReviewResult(
                verdict="APPROVED",
                findings=[],
                summary="Could not parse review response.",
                raw_response=content,
            )
