"""GitLab provider — Git operations via the `glab` CLI and REST API.

Implements GitProvider for GitLab repositories. Uses `glab` CLI as the
primary interface, falling back to GitLab REST API when needed.
GitLab uses "merge requests" (MR) instead of "pull requests" (PR).
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

from app.git.provider import GitProvider

logger = logging.getLogger(__name__)

_GLAB_EXECUTABLE = "glab"


def _check_glab_installed() -> None:
    """Raise RuntimeError if glab CLI is not installed."""
    try:
        result = subprocess.run(
            [_GLAB_EXECUTABLE, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "GitLab CLI (`glab`) is not installed or not on PATH. "
            "Install it from https://gitlab.com/gitlab-org/cli and "
            "authenticate with `glab auth login`."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("GitLab CLI (`glab`) command timed out.")


def _check_glab_auth() -> None:
    """Raise RuntimeError if glab is not authenticated."""
    try:
        result = subprocess.run(
            [_GLAB_EXECUTABLE, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "GitLab CLI is not authenticated. Run `glab auth login` to authenticate."
            )
    except subprocess.TimeoutExpired:
        raise RuntimeError("GitLab CLI auth check timed out.")


async def _run_glab(
    args: list[str],
    cwd: Optional[str] = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    """Run a glab CLI command asynchronously.

    Args:
        args: Command arguments (without 'glab' prefix).
        cwd: Working directory for the command.
        timeout: Command timeout in seconds.

    Returns:
        CompletedProcess with stdout, stderr, returncode.
    """
    cmd = [_GLAB_EXECUTABLE] + args
    logger.debug("Running: %s", " ".join(cmd))

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError(
            f"GitLab CLI command timed out after {timeout}s: glab {' '.join(args)}"
        )

    stdout_str = stdout.decode("utf-8", errors="replace").strip()
    stderr_str = stderr.decode("utf-8", errors="replace").strip()

    if process.returncode != 0:
        error_msg = stderr_str or stdout_str or "Unknown error"
        raise RuntimeError(
            f"GitLab CLI command failed (exit {process.returncode}): "
            f"glab {' '.join(args)}\n{error_msg}"
        )

    return subprocess.CompletedProcess(
        args=cmd,
        returncode=process.returncode,
        stdout=stdout_str,
        stderr=stderr_str,
    )


def _run_git_sync(
    args: list[str],
    cwd: Optional[str] = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    """Run a git command synchronously."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except FileNotFoundError:
        raise RuntimeError("`git` executable not found. Ensure git is installed and on PATH.")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Git command timed out: git {' '.join(args)}")

    if result.returncode != 0:
        raise RuntimeError(
            f"Git command failed (exit {result.returncode}): "
            f"git {' '.join(args)}\n{result.stderr.strip()}"
        )

    return result


class GitLabProvider(GitProvider):
    """Git operations for GitLab repositories via `glab` CLI.

    GitLab-specific quirks:
    - Uses "Merge Request" (MR) instead of "Pull Request" (PR).
      The create_pr() method creates an MR and returns its URL.
    - MR URLs follow the pattern: https://gitlab.com/org/repo/-/merge_requests/42
    - Branch naming recommendations are same as GitHub.
    - Default target branch is typically 'main' (not 'master' on newer projects).

    Usage:
        provider = GitLabProvider()
        await provider.clone("git@gitlab.com:org/repo.git", "./workdir")
        await provider.create_branch("feature/my-change")
        commit_hash = await provider.commit("feat: add feature")
        await provider.push()
        mr_url = await provider.create_pr("feat: add feature", "## Summary\\n...")
    """

    def __init__(self) -> None:
        """Initialize the GitLab provider and verify glab CLI is ready."""
        _check_glab_installed()
        _check_glab_auth()

    async def clone(self, url: str, path: str) -> None:
        """Clone a GitLab repository into the given path.

        Uses git clone directly since glab doesn't wrap clone.
        The glab auth session provides SSH/HTTPS credentials automatically.

        Args:
            url: Repository URL (HTTPS or SSH).
            path: Local directory path to clone into.
        """
        parent = str(Path(path).parent)
        Path(parent).mkdir(parents=True, exist_ok=True)

        _run_git_sync(["clone", url, path], timeout=300)
        logger.info("Cloned %s → %s", url, path)

    async def create_branch(self, name: str) -> None:
        """Create and checkout a new branch.

        Args:
            name: Branch name to create.
        """
        _run_git_sync(["checkout", "-b", name], timeout=30)
        logger.info("Created branch: %s", name)

    async def commit(self, message: str) -> str:
        """Stage all changes and commit with the given message.

        Args:
            message: Commit message.

        Returns:
            The commit hash (7-char short form).
        """
        _run_git_sync(["add", "."], timeout=30)
        result = _run_git_sync(["commit", "-m", message], timeout=30)

        # Handle "nothing to commit" gracefully
        if "nothing to commit" in (result.stdout + result.stderr):
            head = _run_git_sync(["rev-parse", "--short", "HEAD"], timeout=10)
            return head.stdout.strip()

        # Get commit hash
        hash_result = _run_git_sync(["rev-parse", "--short", "HEAD"], timeout=10)
        commit_hash = hash_result.stdout.strip()
        logger.info("Committed: %s (%s)", message, commit_hash)
        return commit_hash

    async def push(self) -> None:
        """Push the current branch to the remote (origin).

        Raises:
            RuntimeError: If push fails.
        """
        branch_result = _run_git_sync(["rev-parse", "--abbrev-ref", "HEAD"], timeout=10)
        branch = branch_result.stdout.strip()

        try:
            _run_git_sync(
                ["push", "--set-upstream", "origin", branch],
                timeout=120,
            )
        except RuntimeError as exc:
            msg = str(exc)
            if "Permission denied" in msg or "Authentication failed" in msg:
                raise RuntimeError(
                    f"Git push failed — authentication error. "
                    f"Ensure your SSH key or token is configured: {msg}"
                )
            if "protected branch" in msg.lower():
                raise RuntimeError(
                    f"Git push failed — branch '{branch}' is protected."
                )
            raise

        logger.info("Pushed branch: %s", branch)

    async def create_pr(self, title: str, body: str) -> str:
        """Create a merge request on GitLab via `glab mr create`.

        GitLab calls these "merge requests" (MR), not "pull requests" (PR).
        This method creates an MR and returns its web URL.

        Args:
            title: MR title.
            body: MR description body (markdown).

        Returns:
            The MR URL (e.g., https://gitlab.com/org/repo/-/merge_requests/42).

        Raises:
            RuntimeError: If MR creation fails.
        """
        try:
            result = subprocess.run(
                [
                    _GLAB_EXECUTABLE,
                    "mr",
                    "create",
                    "--title", title,
                    "--description", body,
                    "--fill",  # Auto-fill details from branch/commits
                    "--yes",   # Skip confirmation prompt
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError:
            raise RuntimeError("GitLab CLI (`glab`) not found on PATH.")

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"Failed to create merge request: {error_msg}"
            )

        mr_url = result.stdout.strip()
        # Extract URL from output
        url_match = re.search(
            r"https://gitlab\.com/[^\s]+/-/merge_requests/\d+", mr_url
        )
        if url_match:
            mr_url = url_match.group(0)

        logger.info("Created MR: %s", mr_url)
        return mr_url
