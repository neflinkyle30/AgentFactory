"""PR Agent role — creates branches, commits, and generates PR descriptions.

The PR agent reads the diff, ticket info, and review findings to produce
a PR title, body, branch name, and conventional commit message.
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

# ── PR Agent system prompt ──────────────────────────────────────────

PR_AGENT_SYSTEM_PROMPT = """You are the PR AGENT for the Agent Factory pipeline.
Your job is to generate Pull Request metadata following conventional commits.

## Input
You will receive:
1. **Diff Summary**: What files were changed and how.
2. **Ticket Info**: Title, description, and acceptance criteria.
3. **Review Findings**: Verdict and dimensional findings from the review.

## Output Format

You MUST respond with valid JSON in this exact structure:
```json
{
  "pr_title": "feat(auth): add JWT-based authentication middleware",
  "pr_body": "## Summary\\n\\nImplements JWT authentication...\\n\\n## Changes\\n...",
  "branch_name": "feature/jwt-auth-middleware",
  "commit_message": "feat(auth): add JWT authentication middleware"
}
```

## Conventional Commit Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding missing tests
- `chore`: Maintenance tasks

## Rules
- PR title must follow conventional commits: `type(scope): description`.
- PR body must include: Summary, Changes list, Testing notes, and Review findings.
- Branch name must be kebab-case with a type prefix (feature/, fix/, chore/).
- Commit message must match the PR title.
- Reference the ticket/issue if a ticket_key is provided.
- All fields are required and must be non-empty.
"""


# ── PR Agent input ──────────────────────────────────────────────────

class PRAgentInput:
    """Input data for the PR phase."""

    def __init__(
        self,
        diff_summary: str = "",
        ticket_title: str = "",
        ticket_description: str = "",
        ticket_key: str = "",
        review_verdict: str = "",
        review_findings: Optional[List[Dict[str, Any]]] = None,
        files_changed: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        self.diff_summary = diff_summary
        self.ticket_title = ticket_title
        self.ticket_description = ticket_description
        self.ticket_key = ticket_key
        self.review_verdict = review_verdict
        self.review_findings = review_findings or []
        self.files_changed = files_changed or []


# ── PR Agent output ─────────────────────────────────────────────────

class PRAgentResult:
    """Structured output from the PR Agent."""

    def __init__(
        self,
        pr_title: str = "",
        pr_body: str = "",
        branch_name: str = "",
        commit_message: str = "",
        raw_response: str = "",
    ) -> None:
        self.pr_title = pr_title
        self.pr_body = pr_body
        self.branch_name = branch_name
        self.commit_message = commit_message
        self.raw_response = raw_response

    @property
    def passed(self) -> bool:
        """True if PR metadata is valid (non-empty, conventional format)."""
        if not all([self.pr_title, self.pr_body, self.branch_name, self.commit_message]):
            return False
        # Check conventional commit format: type(scope): description
        if ":" not in self.pr_title:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pr_title": self.pr_title,
            "pr_body": self.pr_body,
            "branch_name": self.branch_name,
            "commit_message": self.commit_message,
        }


# ── PR Agent Role ───────────────────────────────────────────────────

class PRAgentRole:
    """Executes the PR phase: generates PR metadata for code submission.

    Reads the diff, ticket, and review findings to produce a PR title,
    body, branch name, and conventional commit message.
    """

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    async def execute(
        self,
        pr_input: PRAgentInput,
        db: Optional[AsyncSession] = None,
    ) -> PRAgentResult:
        """Run the PR Agent.

        Args:
            pr_input: Diff summary, ticket info, and review findings.
            db: Optional database session.

        Returns:
            PRAgentResult with PR title, body, branch name, commit message.
        """
        user_message = self._build_user_message(pr_input)

        result = await self._provider.query(
            system_prompt=PR_AGENT_SYSTEM_PROMPT,
            messages=[Message(role="user", content=user_message)],
            thinking=True,
            max_tokens=4000,
        )

        return self._parse_response(result.content)

    async def persist_artifact(
        self,
        result: PRAgentResult,
        run_id: str,
        db: AsyncSession,
    ) -> Artifact:
        """Persist the PR output as an Artifact."""
        import uuid as _uuid

        artifact = Artifact(
            phase_name="PR",
            artifact_type="pr_result",
            content_ref=json.dumps(result.to_dict()),
        )
        artifact.run_id = _uuid.UUID(run_id) if isinstance(run_id, str) else run_id
        db.add(artifact)
        await db.flush()
        return artifact

    # ── Helpers ────────────────────────────────────────────────────

    def _build_user_message(self, pr_input: PRAgentInput) -> str:
        parts = [
            "## PR Generation Request\n",
            f"**Ticket Title**: {pr_input.ticket_title}",
            f"**Ticket Description**: {pr_input.ticket_description}",
        ]

        if pr_input.ticket_key:
            parts.append(f"**Ticket Key**: {pr_input.ticket_key}")

        if pr_input.files_changed:
            parts.append("\n### Files Changed")
            for f in pr_input.files_changed:
                parts.append(
                    f"- `{f.get('path', '?')}` ({f.get('action', 'modified')}): "
                    f"{f.get('description', '')}"
                )
            parts.append("")

        if pr_input.diff_summary:
            parts.append("### Diff Summary")
            parts.append(pr_input.diff_summary[:3000])
            parts.append("")

        parts.append(f"### Review Verdict: {pr_input.review_verdict}")

        if pr_input.review_findings:
            parts.append("### Review Findings")
            for f in pr_input.review_findings:
                parts.append(
                    f"- [{f.get('severity', '?')}] {f.get('dimension', '?')}: "
                    f"{f.get('description', '')}"
                )

        parts.append(
            "\n\nPlease generate the PR title, body, branch name, and commit message "
            "following conventional commits. Return the JSON result."
        )
        return "\n".join(parts)

    def _parse_response(self, content: str) -> PRAgentResult:
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
            return PRAgentResult(
                pr_title=data.get("pr_title", ""),
                pr_body=data.get("pr_body", ""),
                branch_name=data.get("branch_name", ""),
                commit_message=data.get("commit_message", ""),
                raw_response=content,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "Failed to parse PR agent response as JSON: %s. Returning empty result.",
                exc,
            )
            return PRAgentResult(raw_response=content)
