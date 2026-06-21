"""Scope guard — advisory file-change boundary checker.

The ScopeGuard provides WARN-ONLY scope enforcement. It never blocks
implementation — per the user's decision, scope is advisory. All
violations are logged to the events table for human review.

This design enables the pipeline to learn which components are
frequently modified together and refine scope declarations over time.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ScopeWarning:
    """A single scope advisory warning."""

    def __init__(
        self,
        file_path: str,
        declared_components: List[str],
        context: str = "",
    ) -> None:
        self.file_path = file_path
        self.declared_components = declared_components
        self.context = context

    @property
    def message(self) -> str:
        """Human-readable warning message."""
        return (
            f"Scope advisory: {self.file_path} is outside declared "
            f"components {self.declared_components}. Logged for review."
        )

    def to_dict(self) -> Dict[str, str]:
        return {
            "file_path": self.file_path,
            "message": self.message,
            "context": self.context,
        }


class ScopeGuard:
    """Advisory scope checker — WARN-ONLY, never deny.

    Checks whether file changes fall within the declared components
    of a ticket. Always returns allowed=True (per user decision to
    keep scope advisory rather than blocking).

    Usage:
        guard = ScopeGuard()
        allowed, warning = guard.check("src/auth/middleware.py", ["auth", "api"])
        # → (True, None) — within scope

        allowed, warning = guard.check("src/database.py", ["auth", "api"])
        # → (True, "Scope advisory: src/database.py is outside...")

    For batch validation:
        warnings = guard.validate_diff(git_diff_output, ["auth", "api"])
        # → list of ScopeWarning for files outside scope
    """

    def __init__(self) -> None:
        """Initialize the scope guard. No configuration needed."""
        pass

    def check(
        self,
        file_path: str,
        declared_components: List[str],
        *,
        context: str = "",
    ) -> Tuple[bool, Optional[str]]:
        """Check if a file path falls within the declared components.

        NEVER denies — always returns allowed=True. The advisory
        message is for logging and human review only.

        Args:
            file_path: The relative path to the file being changed.
            declared_components: List of component names declared
                in the ticket (e.g., ["auth", "api", "frontend"]).
            context: Optional context string for the warning
                (e.g., "T-011: auth middleware").

        Returns:
            Tuple of (allowed: True, warning: str | None).
        """
        if not declared_components:
            # No components declared — warn about everything
            warning = ScopeWarning(file_path, ["none declared"], context)
            return (True, warning.message)

        if self._is_within_scope(file_path, declared_components):
            return (True, None)

        warning = ScopeWarning(file_path, declared_components, context)
        return (True, warning.message)

    def validate_diff(
        self,
        diff_output: str,
        declared_components: List[str],
    ) -> List[ScopeWarning]:
        """Scan a git diff for files outside the declared scope.

        Parses the git diff output to extract changed file paths,
        then checks each one against the declared components.

        Args:
            diff_output: Raw git diff text (from `git diff --name-only`).
            declared_components: List of component names declared
                in the ticket.

        Returns:
            List of ScopeWarning for files outside the declared scope.
            Empty list means all changes are within scope.
        """
        if not diff_output.strip():
            return []

        # Parse file paths from diff output
        # Each line is a relative file path
        changed_files = self._parse_diff_files(diff_output)

        warnings: List[ScopeWarning] = []
        for file_path in changed_files:
            if not self._is_within_scope(file_path, declared_components):
                warning = ScopeWarning(
                    file_path=file_path,
                    declared_components=declared_components,
                    context=f"diff scan: {len(changed_files)} files changed",
                )
                warnings.append(warning)

        return warnings

    def check_all(
        self,
        files_changed: List[Dict[str, str]],
        declared_components: List[str],
    ) -> List[ScopeWarning]:
        """Check multiple file paths from a DevelopResult.files_changed list.

        Args:
            files_changed: List of dicts with 'path' key (from DevelopResult).
            declared_components: List of component names.

        Returns:
            List of ScopeWarning for files outside scope.
        """
        warnings: List[ScopeWarning] = []
        for entry in files_changed:
            file_path = entry.get("path", "")
            if file_path and not self._is_within_scope(file_path, declared_components):
                warning = ScopeWarning(
                    file_path=file_path,
                    declared_components=declared_components,
                    context=f"action: {entry.get('action', 'unknown')}",
                )
                warnings.append(warning)
        return warnings

    # ── Internal helpers ──────────────────────────────────────────

    @staticmethod
    def _is_within_scope(
        file_path: str,
        declared_components: List[str],
    ) -> bool:
        """Determine if a file path is within any of the declared components.

        Uses prefix matching: the file path must start with one of the
        component names (as a directory or module prefix).

        Examples:
            "src/auth/routes.py" in ["auth"] → True (starts with "auth" in path)
            "src/database/models.py" in ["auth", "api"] → False
            "frontend/src/App.tsx" in ["frontend"] → True
        """
        normalized_path = file_path.replace("\\", "/").lower()
        normalized_components = [c.lower() for c in declared_components]

        for component in normalized_components:
            # Match if the path starts with the component as a prefix segment
            # e.g., "src/auth/..." should match component "auth"
            if component in normalized_path:
                return True

            # Also match exact prefix (e.g., "frontend/src" with "frontend")
            if normalized_path.startswith(component + "/") or normalized_path.startswith(component + "\\"):
                return True

        return False

    @staticmethod
    def _parse_diff_files(diff_output: str) -> List[str]:
        """Extract file paths from git diff --name-only output.

        Args:
            diff_output: Raw git diff --name-only output, one file per line.

        Returns:
            List of relative file paths.
        """
        files: List[str] = []
        for line in diff_output.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("diff ") and not line.startswith("---") and not line.startswith("+++"):
                # Filter out git metadata lines
                if not any(line.startswith(prefix) for prefix in ("index ", "@@", "\\ ", "rename ", "copy ", "similarity ")):
                    files.append(line)
        return files
