"""Verify role — runs in a fresh session and tests the implementation.

The Verify agent describes the test strategy, runs tests, and collects
evidence (screenshots, API traces) to prove the implementation works.
In MVP, tests are described rather than executed (execution in Phase 3).
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

# ── Verify system prompt ────────────────────────────────────────────

VERIFY_SYSTEM_PROMPT = """You are the VERIFICATION AGENT for the Agent Factory pipeline.
Your job is to test the implementation against the acceptance criteria
and produce a test results report.

## Input
You will receive:
1. **Work Directory**: The path to the working copy of the code.
2. **Acceptance Criteria**: The formal requirements to verify against.

## Output Format

You MUST respond with valid JSON in this exact structure:
```json
{
  "test_results": [
    {
      "ac_index": 1,
      "test_name": "User can login with valid credentials",
      "passed": true,
      "evidence_type": "manual",
      "output": "Test passed: login endpoint returns 200 with JWT token"
    }
  ],
  "screenshot_paths": [],
  "api_traces": [],
  "summary": "All 3 acceptance criteria verified. 3/3 tests passed.",
  "total_tests": 3,
  "passed_tests": 3
}
```

## Rules
- Each acceptance criterion must have at least one test.
- test_name must be descriptive and specific.
- evidence_type must be one of: "manual", "automated", "screenshot", "api_trace".
- In MVP, tests are described (actual execution comes in Phase 3).
- All tests must pass for the verification to succeed.
- Screenshot paths should be relative to the work directory.
- API traces should show request/response pairs for endpoint verification.
"""


# ── Verify input ────────────────────────────────────────────────────

class VerifyInput:
    """Input data for the Verify phase."""

    def __init__(
        self,
        workdir: str = "",
        acceptance_criteria: Optional[List[Dict[str, Any]]] = None,
        requirements: Optional[List[Dict[str, Any]]] = None,
        spec_output: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.workdir = workdir
        self.acceptance_criteria = acceptance_criteria or []
        self.requirements = requirements or []
        self.spec_output = spec_output or {}


# ── Verify output ───────────────────────────────────────────────────

class VerifyResult:
    """Structured output from the Verify agent."""

    def __init__(
        self,
        test_results: Optional[List[Dict[str, Any]]] = None,
        screenshot_paths: Optional[List[str]] = None,
        api_traces: Optional[List[Dict[str, Any]]] = None,
        summary: str = "",
        total_tests: int = 0,
        passed_tests: int = 0,
        raw_response: str = "",
    ) -> None:
        self.test_results = test_results or []
        self.screenshot_paths = screenshot_paths or []
        self.api_traces = api_traces or []
        self.summary = summary
        self.total_tests = total_tests
        self.passed_tests = passed_tests
        self.raw_response = raw_response

    @property
    def passed(self) -> bool:
        """True if all ACs have at least one passing test."""
        if not self.test_results:
            return False
        return all(t.get("passed", False) for t in self.test_results)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_results": self.test_results,
            "screenshot_paths": self.screenshot_paths,
            "api_traces": self.api_traces,
            "summary": self.summary,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
        }


# ── Verify Role ─────────────────────────────────────────────────────

class VerifyRole:
    """Executes the Verify phase: tests implementation against acceptance criteria.

    Describes test strategies for each AC, collects evidence, and produces
    a pass/fail report. In MVP, describes tests; actual execution in Phase 3.
    """

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    async def execute(
        self,
        verify_input: VerifyInput,
        db: Optional[AsyncSession] = None,
    ) -> VerifyResult:
        """Run the Verify agent.

        Args:
            verify_input: Workdir, acceptance criteria, and requirements.
            db: Optional database session.

        Returns:
            VerifyResult with test results, screenshots, and API traces.
        """
        user_message = self._build_user_message(verify_input)

        result = await self._provider.query(
            system_prompt=VERIFY_SYSTEM_PROMPT,
            messages=[Message(role="user", content=user_message)],
            thinking=True,
            max_tokens=4000,
        )

        return self._parse_response(result.content)

    async def persist_artifact(
        self,
        result: VerifyResult,
        run_id: str,
        db: AsyncSession,
    ) -> Artifact:
        """Persist the verify output as an Artifact."""
        import uuid as _uuid

        artifact = Artifact(
            phase_name="VERIFY",
            artifact_type="verify_result",
            content_ref=json.dumps(result.to_dict()),
        )
        artifact.run_id = _uuid.UUID(run_id) if isinstance(run_id, str) else run_id
        db.add(artifact)
        await db.flush()
        return artifact

    # ── Helpers ────────────────────────────────────────────────────

    def _build_user_message(self, verify_input: VerifyInput) -> str:
        parts = [
            "## Verification Request\n",
            f"**Work Directory**: {verify_input.workdir or settings.runs_directory}",
        ]

        if verify_input.acceptance_criteria:
            parts.append("\n### Acceptance Criteria")
            for i, ac in enumerate(verify_input.acceptance_criteria, 1):
                if isinstance(ac, dict):
                    parts.append(
                        f"{i}. Given {ac.get('given', '?')}, "
                        f"When {ac.get('when', '?')}, "
                        f"Then {ac.get('then', '?')}"
                    )
                else:
                    parts.append(f"{i}. {ac}")

        if verify_input.requirements:
            parts.append("\n### Requirements")
            for req in verify_input.requirements:
                req_id = req.get("id", "?")
                shall = req.get("shall_text", "")
                parts.append(f"- **{req_id}**: {shall}")

        parts.append(
            "\n\nPlease describe the test strategy for each acceptance criterion, "
            "including test names, expected evidence types, and pass/fail status. "
            "Return the JSON result."
        )
        return "\n".join(parts)

    def _parse_response(self, content: str) -> VerifyResult:
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
            return VerifyResult(
                test_results=data.get("test_results", []),
                screenshot_paths=data.get("screenshot_paths", []),
                api_traces=data.get("api_traces", []),
                summary=data.get("summary", ""),
                total_tests=int(data.get("total_tests", 0)),
                passed_tests=int(data.get("passed_tests", 0)),
                raw_response=content,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "Failed to parse verify response as JSON: %s. Returning empty result.",
                exc,
            )
            return VerifyResult(
                test_results=[],
                summary="",
                raw_response=content,
            )
