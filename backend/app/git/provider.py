"""Git provider ABC and GitHub stub implementation.

Abstract base class for Git operations: clone, create_branch, commit,
push, create_pr. Includes a detect_provider() function and a GitHub
stub returning mock values for MVP. Real implementations in Phase 2.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class GitProvider(ABC):
    """Abstract base class for Git operations.

    Implementations must provide clone, create_branch, commit, push,
    and create_pr. Used by the PR phase to create branches and PRs.
    """

    @abstractmethod
    async def clone(self, url: str, path: str) -> None:
        """Clone a repository from url into path.

        Args:
            url: Remote repository URL.
            path: Local directory path to clone into.
        """
        ...

    @abstractmethod
    async def create_branch(self, name: str) -> None:
        """Create and checkout a new branch.

        Args:
            name: Branch name to create.
        """
        ...

    @abstractmethod
    async def commit(self, message: str) -> str:
        """Commit staged changes with the given message.

        Args:
            message: Commit message.

        Returns:
            The commit hash.
        """
        ...

    @abstractmethod
    async def push(self) -> None:
        """Push the current branch to the remote."""
        ...

    @abstractmethod
    async def create_pr(self, title: str, body: str) -> str:
        """Create a pull request on the remote.

        Args:
            title: PR title.
            body: PR description body.

        Returns:
            The PR URL.
        """
        ...


def detect_provider() -> str:
    """Detect the Git hosting provider from the remote URL.

    Returns one of: "github", "gitlab", "bitbucket".
    Defaults to "github" if detection fails.
    """
    import os
    import subprocess
    import sys

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        url = result.stdout.strip().lower()

        if "github.com" in url:
            return "github"
        elif "gitlab.com" in url or "gitlab" in url:
            return "gitlab"
        elif "bitbucket.org" in url:
            return "bitbucket"
    except Exception:
        pass

    return "github"


# ── GitHub Stub (MVP) ─────────────────────────────────────────────


class GitHubStubProvider(GitProvider):
    """GitHub provider stub returning mock values for MVP.

    Real Git operations will be implemented in Phase 2 (T-035-037).
    This stub returns deterministic mock values so the pipeline
    can complete without real repository access.
    """

    async def clone(self, url: str, path: str) -> None:
        """Stub: log the clone operation, do nothing."""
        logger.info("[STUB] git clone %s → %s", url, path)
        import os as _os
        _os.makedirs(path, exist_ok=True)

    async def create_branch(self, name: str) -> None:
        """Stub: log branch creation."""
        logger.info("[STUB] git checkout -b %s", name)

    async def commit(self, message: str) -> str:
        """Stub: return a mock commit hash."""
        import hashlib
        import uuid

        mock_hash = hashlib.sha256(
            (message + str(uuid.uuid4())).encode()
        ).hexdigest()[:7]
        logger.info("[STUB] git commit -m \"%s\" → %s", message, mock_hash)
        return mock_hash

    async def push(self) -> None:
        """Stub: log push operation."""
        logger.info("[STUB] git push origin HEAD")

    async def create_pr(self, title: str, body: str) -> str:
        """Stub: return a mock PR URL."""
        import uuid

        pr_number = str(uuid.uuid4())[:8]
        pr_url = f"https://github.com/agent-factory/mock/pull/{pr_number}"
        logger.info("[STUB] Create PR: %s → %s", title, pr_url)
        return pr_url


def get_git_provider(
    provider_name: Optional[str] = None,
    *,
    mock: bool = False,
) -> GitProvider:
    """Factory: return the configured Git provider.

    Args:
        provider_name: Override the detected provider. If None, auto-detect.
        mock: If True, return the stub provider (no real Git operations).

    Returns:
        A GitProvider instance for the detected/configured provider.

    Raises:
        RuntimeError: If the provider's CLI/tooling is not installed.
    """
    if mock:
        return GitHubStubProvider()

    if provider_name is None:
        provider_name = detect_provider()

    provider_map = {
        "github": "app.git.github.GitHubProvider",
        "gitlab": "app.git.gitlab.GitLabProvider",
        "bitbucket": "app.git.bitbucket.BitbucketProvider",
    }

    import_path = provider_map.get(provider_name.lower())
    if import_path is None:
        logger.warning(
            "Unknown provider '%s', falling back to GitHub stub", provider_name
        )
        return GitHubStubProvider()

    # Lazy-import to avoid loading all providers upfront
    try:
        import importlib

        module_name, class_name = import_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        provider_class = getattr(module, class_name)
        return provider_class()
    except RuntimeError:
        # Re-raise runtime errors from provider init (e.g., CLI not installed)
        raise
    except Exception as exc:
        logger.exception("Failed to initialize %s: %s", provider_name, exc)
        raise RuntimeError(
            f"Failed to initialize Git provider '{provider_name}': {exc}"
        ) from exc
