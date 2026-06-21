"""Mock AI provider — returns deterministic responses for development/testing.

Activated when AGENT_FACTORY_MOCK=1. No API calls are made.
Useful for testing pipeline flow without API costs.
"""

from typing import Any, AsyncIterator, Dict, List, Optional

from app.adapters.base import (
    AIProvider,
    Message,
    ResultMessage,
    TokenUsage,
    ToolCall,
)

# ── Mock responses per phase/role ──────────────────────────────────
# Each role gets a deterministic canned response so pipeline tests
# can verify behavior without depending on an LLM.

_MOCK_RESPONSES: Dict[str, str] = {
    "intake": (
        "## Intake Analysis\n\n"
        "**Completeness Score**: 92/100\n\n"
        "### Normalized Ticket\n"
        "- Title: Add user authentication with JWT\n"
        "- Description: Implement login, registration, and token refresh\n"
        "- Priority: high\n"
        "- Components: [auth, api, frontend]\n\n"
        "### Evaluation\n"
        "- AC presence (40/40): 3 well-formed Given-When-Then criteria\n"
        "- Description clarity (25/25): Clear and specific\n"
        "- Title specificity (15/15): Descriptive and searchable\n"
        "- Priority (10/10): Correctly set to high\n"
        "- Components (10/10): All affected areas identified\n\n"
        "**Verdict**: PASS — proceed to SPEC phase."
    ),
    "spec": (
        "## Specification\n\n"
        "### Requirements\n\n"
        "#### REQ-1: User Registration\n"
        "The system SHALL allow users to create an account with email and password.\n\n"
        "**Scenario**: Successful registration\n"
        "- **Given** a new user with a valid email and password\n"
        "- **When** the user submits the registration form\n"
        "- **Then** an account is created, a verification email is sent, "
        "and the user is redirected to login.\n\n"
        "**Scenario**: Duplicate email\n"
        "- **Given** a user with email already in the system\n"
        "- **When** registration is attempted with the same email\n"
        "- **Then** an error is returned with code DUPLICATE_EMAIL.\n\n"
        "#### REQ-2: User Login\n"
        "The system SHALL authenticate users and issue JWT tokens.\n\n"
        "**Scenario**: Successful login\n"
        "- **Given** a registered user with valid credentials\n"
        "- **When** the user submits the login form\n"
        "- **Then** an access token and refresh token are returned.\n\n"
        "### Coverage Map\n"
        "- AC-1 → REQ-1\n"
        "- AC-2 → REQ-2\n"
        "- AC-3 → REQ-2 (token refresh scenario)\n\n"
        "**Coverage**: 100% — all ACs mapped."
    ),
    "design": (
        "## Technical Design\n\n"
        "### Architecture Decisions\n\n"
        "| Decision | Choice | Rationale |\n"
        "|----------|--------|----------|\n"
        "| Auth library | PyJWT + passlib | Lightweight, no external deps |\n"
        "| Token storage | httpOnly cookie + memory | XSS-safe, CSRF-protected |\n\n"
        "### Files Referenced\n"
        "- `src/auth/middleware.py` (new)\n"
        "- `src/auth/routes.py` (new)\n"
        "- `src/auth/models.py` (new)\n"
        "- `src/config.py` (modify)\n"
        "- `src/app.py` (modify)\n\n"
        "### Components\n"
        "- `auth`: JWT middleware, login/register routes\n"
        "- `api`: Protected endpoints requiring auth\n"
        "- `frontend`: Login/register forms, auth context\n\n"
        "### Tasks\n"
        "- T-001: Create auth models (User, Token)\n"
        "- T-002: Implement JWT middleware\n"
        "- T-003: Add login/register routes\n"
        "- T-004: Update app config\n"
        "- T-005: Wire frontend auth context\n\n"
        "**AC Coverage**: 100% (3/3 ACs mapped to tasks)"
    ),
    "tasks": (
        "## Task Breakdown\n\n"
        "### Task List\n\n"
        "| ID | Description | Files | ACs | Complexity |\n"
        "|----|------------|-------|-----|------------|\n"
        "| T-001 | Create User model with email/password fields | src/auth/models.py | AC-1 | small |\n"
        "| T-002 | Implement password hashing with bcrypt | src/auth/utils.py | AC-1 | small |\n"
        "| T-003 | Add JWT encode/decode helpers | src/auth/jwt.py | AC-2 | small |\n"
        "| T-004 | Implement login endpoint | src/auth/routes.py | AC-2 | medium |\n"
        "| T-005 | Implement register endpoint | src/auth/routes.py | AC-1 | medium |\n"
        "| T-006 | Add auth middleware to app | src/auth/middleware.py | AC-2,AC-3 | medium |\n"
        "| T-007 | Update config with JWT settings | src/config.py | AC-2 | small |\n\n"
        "### Coverage\n"
        "- REQ-1 → T-001, T-002, T-005\n"
        "- REQ-2 → T-003, T-004, T-006, T-007\n\n"
        "**All requirements covered. No circular dependencies.**"
    ),
    "develop": (
        "## Development Summary\n\n"
        "### Files Modified\n"
        "- `src/auth/models.py` — Created User model\n"
        "- `src/auth/middleware.py` — JWT validation middleware\n"
        "- `src/auth/routes.py` — Login and register endpoints\n"
        "- `src/config.py` — Added JWT_SECRET and token expiry\n"
        "- `src/app.py` — Registered auth blueprint\n\n"
        "### Build Result\n"
        "- Build: ✅ PASS (exit code 0)\n"
        "- Lint: ✅ PASS (exit code 0)\n\n"
        "### Tests Added\n"
        "- test_login_success\n"
        "- test_login_invalid_credentials\n"
        "- test_register_creates_user\n"
        "- test_protected_route_requires_auth\n\n"
        "**All tasks complete. Ready for verification.**"
    ),
    "verify": (
        "## Verification Report\n\n"
        "### Test Results\n\n"
        "| Test | AC | Status |\n"
        "|------|----|--------|\n"
        "| test_register_creates_user | AC-1 | ✅ PASS |\n"
        "| test_login_success | AC-2 | ✅ PASS |\n"
        "| test_login_invalid_credentials | AC-2 | ✅ PASS |\n"
        "| test_token_refresh | AC-3 | ✅ PASS |\n"
        "| test_protected_route_requires_auth | AC-2 | ✅ PASS |\n\n"
        "### Coverage\n"
        "- Tests per AC: 3/3 ACs have ≥1 passing test\n"
        "- Suite pass: ✅ All tests green\n\n"
        "### Evidence\n"
        "- Screenshots: 2 captured\n"
        "- API responses: 4 captured\n\n"
        "**Verdict**: PASSED — all ACs verified."
    ),
    "review": (
        "## Code Review\n\n"
        "### Findings\n\n"
        "| # | Severity | Category | File | Line | Description |\n"
        "|---|----------|----------|------|------|-------------|\n"
        "| 1 | SUGGESTION | Quality | src/auth/routes.py | 45 | Consider adding rate limiting to login endpoint |\n"
        "| 2 | SUGGESTION | Quality | src/auth/models.py | 12 | Add docstring to User model |\n"
        "| 3 | OK | — | — | — | Security scan: no secrets detected |\n"
        "| 4 | OK | — | — | — | SQL injection: all queries parameterized |\n"
        "| 5 | OK | — | — | — | XSS: input properly sanitized |\n\n"
        "### Verdict\n"
        "- Security: ✅ Clean\n"
        "- Integrity: ✅ Clean\n"
        "- Performance: ✅ Acceptable\n"
        "- Architecture: ✅ Conventions followed\n"
        "- Quality: ⚠️ 2 suggestions\n\n"
        "**Verdict**: APPROVED_WITH_SUGGESTIONS"
    ),
    "pr": (
        "## PR Summary\n\n"
        "### Pull Request Created\n"
        "- **PR URL**: https://github.com/example/repo/pull/42\n"
        "- **Branch**: agent-factory/PROJ-123\n"
        "- **Base**: main\n\n"
        "### Changes\n"
        "- 5 files modified, 3 new files\n"
        "- +245 lines, -12 lines\n\n"
        "### Tests\n"
        "- 5 tests added, 5 passed\n"
        "- All acceptance criteria verified\n\n"
        "### Evidence\n"
        "- Screenshots: [screenshot-1.png], [screenshot-2.png]\n"
        "- API responses: 4 captured\n"
        "- Review: APPROVED_WITH_SUGGESTIONS (2 suggestions)\n\n"
        "**Status**: DONE ✅"
    ),
    "default": (
        "This is a mock response from the Agent Factory MockProvider.\n"
        "Set AGENT_FACTORY_MOCK=0 to use the real DeepSeek API.\n"
    ),
}


class MockProvider(AIProvider):
    """Mock AI provider for development and pipeline testing.

    Returns deterministic canned responses based on the system prompt content.
    Never makes real API calls. Activated by AGENT_FACTORY_MOCK=1.
    """

    def __init__(self) -> None:
        """Initialize the mock provider. No configuration needed."""
        pass

    async def query(
        self,
        system_prompt: str,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        output_format: Optional[Dict[str, Any]] = None,
        thinking: bool = True,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> ResultMessage:
        """Return a deterministic mock response based on the system prompt.

        The mock content is selected by matching keywords in the system prompt
        against known role names (intake, spec, design, etc.).
        """
        content = self._select_mock_content(system_prompt)
        usage = TokenUsage(
            prompt_tokens=self.count_tokens(system_prompt),
            completion_tokens=self.count_tokens(content),
            total_tokens=0,
            cost_usd=0.0,  # Mock mode costs nothing
        )
        usage.total_tokens = usage.prompt_tokens + usage.completion_tokens

        return ResultMessage(
            content=content,
            tool_calls=[],
            usage=usage,
            finish_reason="stop",
            model="mock/deepseek-chat",
        )

    async def query_stream(
        self,
        system_prompt: str,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        thinking: bool = True,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream the mock response in chunks to simulate real streaming."""
        content = self._select_mock_content(system_prompt)
        # Yield in word-sized chunks for realistic streaming feel
        chunk_size = 20
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]

    def count_tokens(self, text: str) -> int:
        """Mock token counting — uses character-based estimation."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def calculate_cost(
        self, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Mock cost — always zero."""
        return 0.0

    # ── Helpers ────────────────────────────────────────────────────

    def _select_mock_content(self, system_prompt: str) -> str:
        """Select the appropriate mock response by keyword matching.

        Scans the system prompt (case-insensitive) for role keywords.
        Uses word-boundary matching to avoid false positives
        (e.g., "respect" should not match "spec").
        """
        import re

        prompt_lower = system_prompt.lower()

        # ── Explicit role markers (first sentence patterns) ───────
        # These are the strongest signals — the system prompt explicitly
        # declares the agent role in its opening line.
        role_markers = [
            (r"you are the intake agent", "intake"),
            (r"you are a developer agent", "develop"),
            (r"you are the specification agent", "spec"),
            (r"you are the design agent", "design"),
            (r"you are the task planner agent", "tasks"),
            (r"you are the verification agent", "verify"),
            (r"you are the review agent", "review"),
            (r"you are the pr agent", "pr"),
        ]

        for pattern, role_key in role_markers:
            if re.search(pattern, prompt_lower):
                return _MOCK_RESPONSES[role_key]

        # ── Fallback: generic keyword matching with word boundaries ──
        # Use word boundaries (\b) to prevent "respect" → "spec", etc.
        keyword_map = [
            (r"\bintake\b", "intake"),
            (r"\bdevelop\b", "develop"),
            (r"\bspec\b", "spec"),
            (r"\bdesign\b", "design"),
            (r"\btasks\b", "tasks"),
            (r"\bverify\b", "verify"),
            (r"\breview\b", "review"),
            (r"\bpr\b", "pr"),
            (r"pr.agent|pr agent", "pr"),
            (r"pull request", "pr"),
        ]

        for pattern, role_key in keyword_map:
            if re.search(pattern, prompt_lower):
                return _MOCK_RESPONSES[role_key]

        return _MOCK_RESPONSES["default"]
