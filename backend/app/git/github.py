"""GitHub provider — Git operations via the `gh` CLI.

Implements GitProvider for GitHub repositories. All operations delegate
to the `gh` command-line tool, which handles authentication via
OAuth tokens stored in the gh config (~/.config/gh/hosts.yml).
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

# ── Helpers ────────────────────────────────────────────────────────

_GH_EXECUTABLE = "gh"
_GH_MIN_VERSION = (2, 0, 0)  # Minimum gh CLI version required


def _check_gh_installed() -> None:
    """Raise RuntimeError if gh CLI is not installed or too old."""
    try:
        result = subprocess.run(
            [_GH_EXECUTABLE, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "GitHub CLI (`gh`) is not installed or not on PATH. "
            "Install it from https://cli.github.com/ and authenticate with `gh auth login`."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("GitHub CLI (`gh`) command timed out. Check your installation.")

    # Check minimum version
    match = re.search(r"gh version (\d+)\.(\d+)\.(\d+)", result.stdout)
    if match:
        major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if (major, minor, patch) < _GH_MIN_VERSION:
            raise RuntimeError(
                f"GitHub CLI version {major}.{minor}.{patch} is too old. "
                f"Minimum required: {_GH_MIN_VERSION[0]}.{_GH_MIN_VERSION[1]}.{_GH_MIN_VERSION[2]}. "
                "Upgrade with: winget install GitHub.cli"
            )


def _check_gh_auth() -> None:
    """Raise RuntimeError if gh is not authenticated."""
    try:
        result = subprocess.run(
            [_GH_EXECUTABLE, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "GitHub CLI is not authenticated. Run `gh auth login` to authenticate."
            )
    except subprocess.TimeoutExpired:
        raise RuntimeError("GitHub CLI auth check timed out.")


async def _run_gh(
    args: list[str],
    cwd: Optional[str] = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    """Run a gh CLI command asynchronously.

    Args:
        args: Command arguments (without 'gh' prefix).
        cwd: Working directory for the command.
        timeout: Command timeout in seconds.

    Returns:
        CompletedProcess with stdout, stderr, returncode.

    Raises:
        RuntimeError: If the command fails.
    """
    cmd = [_GH_EXECUTABLE] + args
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
            f"GitHub CLI command timed out after {timeout}s: gh {' '.join(args)}"
        )

    stdout_str = stdout.decode("utf-8", errors="replace").strip()
    stderr_str = stderr.decode("utf-8", errors="replace").strip()

    if process.returncode != 0:
        error_msg = stderr_str or stdout_str or "Unknown error"
        raise RuntimeError(
            f"GitHub CLI command failed (exit {process.returncode}): "
            f"gh {' '.join(args)}\n{error_msg}"
        )

    return subprocess.CompletedProcess(
        args=cmd,
        returncode=process.returncode,
        stdout=stdout_str,
        stderr=stderr_str,
    )


def _run_gh_sync(
    args: list[str],
    cwd: Optional[str] = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    """Run a gh CLI command synchronously (for clone, which needs real fs state).

    Args:
        args: Command arguments (without 'gh' prefix).
        cwd: Working directory for the command.
        timeout: Command timeout in seconds.

    Returns:
        CompletedProcess with stdout, stderr, returncode.

    Raises:
        RuntimeError: If the command fails.
    """
    cmd = [_GH_EXECUTABLE] + args
    logger.debug("Running (sync): %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except FileNotFoundError:
        raise RuntimeError("GitHub CLI (`gh`) not found on PATH.")
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"GitHub CLI command timed out after {timeout}s: gh {' '.join(args)}"
        )

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        raise RuntimeError(
            f"GitHub CLI command failed (exit {result.returncode}): "
            f"gh {' '.join(args)}\n{error_msg}"
        )

    return result


# ── GitHub Provider ────────────────────────────────────────────────


class GitHubProvider(GitProvider):
    """Git operations for GitHub repositories via the `gh` CLI.

    Uses `gh repo clone`, `gh pr create`, etc. Authentication is
    handled by the gh CLI's built-in OAuth token storage.

    Usage:
        provider = GitHubProvider()
        await provider.clone("https://github.com/org/repo", "./workdir")
        await provider.create_branch("feature/my-change")
        commit_hash = await provider.commit("feat: add feature")
        await provider.push()
        pr_url = await provider.create_pr("feat: add feature", "## Summary\\n...")
    """

    def __init__(self) -> None:
        """Initialize the GitHub provider and verify gh CLI is ready."""
        _check_gh_installed()
        _check_gh_auth()

    async def clone(self, url: str, path: str) -> None:
        """Clone a GitHub repository into the given path.

        Args:
            url: Repository URL (HTTPS or SSH).
            path: Local directory path to clone into.

        Raises:
            RuntimeError: If clone fails (auth, network, etc.).
        """
        parent = str(Path(path).parent)
        Path(parent).mkdir(parents=True, exist_ok=True)

        # Use sync subprocess for clone since it creates files needed
        # by subsequent git operations immediately.
        _run_gh_sync(["repo", "clone", url, path], timeout=300)
        logger.info("Cloned %s → %s", url, path)

    async def create_branch(self, name: str) -> None:
        """Create and checkout a new branch using git (via gh repo context).

        gh doesn't have a direct 'branch create' command for arbitrary repos.
        We use `git checkout -b` within the cloned repo.

        Args:
            name: Branch name to create.

        Raises:
            RuntimeError: If branch creation fails.
        """
        import subprocess as _sync_sp

        try:
            _sync_sp.run(
                ["git", "checkout", "-b", name],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
        except _sync_sp.CalledProcessError as exc:
            raise RuntimeError(
                f"Failed to create branch '{name}': {exc.stderr.strip()}"
            )
        except FileNotFoundError:
            raise RuntimeError("`git` executable not found. Ensure git is installed and on PATH.")
        logger.info("Created branch: %s", name)

    async def commit(self, message: str) -> str:
        """Stage all changes and commit with the given message.

        Args:
            message: Commit message (should follow conventional commits).

        Returns:
            The commit hash (7-char short form).

        Raises:
            RuntimeError: If commit fails (no changes, etc.).
        """
        import subprocess as _sync_sp

        # Stage all changes
        try:
            _sync_sp.run(
                ["git", "add", "."],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
        except _sync_sp.CalledProcessError as exc:
            raise RuntimeError(
                f"Failed to stage changes: {exc.stderr.strip()}"
            )

        # Commit
        try:
            result = _sync_sp.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                # Check if it's "nothing to commit" (benign)
                if "nothing to commit" in result.stderr or "nothing to commit" in result.stdout:
                    # Return HEAD commit hash
                    head_result = _sync_sp.run(
                        ["git", "rev-parse", "--short", "HEAD"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=True,
                    )
                    return head_result.stdout.strip()
                raise RuntimeError(
                    f"Failed to commit: {result.stderr.strip()}"
                )
        except _sync_sp.CalledProcessError:
            raise

        # Get the commit hash
        hash_result = _sync_sp.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        commit_hash = hash_result.stdout.strip()
        logger.info("Committed: %s (%s)", message, commit_hash)
        return commit_hash

    async def push(self) -> None:
        """Push the current branch to the remote (origin).

        Uses git push since gh doesn't wrap this. Sets upstream tracking.

        Raises:
            RuntimeError: If push fails.
        """
        import subprocess as _sync_sp

        # Get current branch name
        branch_result = _sync_sp.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        branch = branch_result.stdout.strip()

        try:
            _sync_sp.run(
                ["git", "push", "--set-upstream", "origin", branch],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
        except _sync_sp.CalledProcessError as exc:
            stderr = exc.stderr.strip()
            # Detect common auth errors
            if "Permission denied" in stderr or "Authentication failed" in stderr:
                raise RuntimeError(
                    f"Git push failed — authentication error. "
                    f"Ensure your SSH key or token is configured: {stderr}"
                )
            if "protected branch" in stderr.lower():
                raise RuntimeError(
                    f"Git push failed — branch '{branch}' is protected. "
                    f"Push to a feature branch instead."
                )
            raise RuntimeError(f"Git push failed: {stderr}")

        logger.info("Pushed branch: %s", branch)

    async def create_pr(self, title: str, body: str) -> str:
        """Create a pull request on GitHub via `gh pr create`.

        Args:
            title: PR title (conventional commit format recommended).
            body: PR description body (markdown).

        Returns:
            The PR URL (e.g., https://github.com/org/repo/pull/42).

        Raises:
            RuntimeError: If PR creation fails.
        """
        import subprocess as _sync_sp

        try:
            result = _sync_sp.run(
                [
                    _GH_EXECUTABLE,
                    "pr",
                    "create",
                    "--title", title,
                    "--body", body,
                    "--fill",  # Use commit messages as defaults for empty fields
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError:
            raise RuntimeError("GitHub CLI (`gh`) not found on PATH.")

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            # Detect common issues
            if "no pull requests" in error_msg.lower() and "found" in error_msg.lower():
                raise RuntimeError(
                    "No pull request template found, but PR creation should still work. "
                    f"Error: {error_msg}"
                )
            raise RuntimeError(
                f"Failed to create PR: {error_msg}"
            )

        pr_url = result.stdout.strip()
        # Extract URL from output (gh sometimes includes extra text)
        url_match = re.search(r"https://github\.com/[^\s]+/pull/\d+", pr_url)
        if url_match:
            pr_url = url_match.group(0)

        logger.info("Created PR: %s", pr_url)
        return pr_url
