"""Bitbucket provider — Git operations via Bitbucket REST API.

Implements GitProvider for Bitbucket Cloud repositories. Uses the
Bitbucket REST API v2.0 for PR creation and git CLI for local operations.
No first-party CLI tool is assumed (Bitbucket doesn't have an official
CLI like gh/glab on all platforms).

Authentication: Requires BITBUCKET_USERNAME and BITBUCKET_APP_PASSWORD
environment variables. Bitbucket uses App Passwords (not OAuth tokens)
for API authentication.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import httpx

from app.git.provider import GitProvider

logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────


def _get_bitbucket_credentials() -> tuple[str, str]:
    """Get Bitbucket credentials from environment.

    Returns:
        (username, app_password) tuple.

    Raises:
        RuntimeError: If credentials are not configured.
    """
    username = os.environ.get("BITBUCKET_USERNAME", "")
    app_password = os.environ.get("BITBUCKET_APP_PASSWORD", "")

    if not username or not app_password:
        raise RuntimeError(
            "Bitbucket credentials not configured. "
            "Set BITBUCKET_USERNAME and BITBUCKET_APP_PASSWORD environment variables. "
            "Create an App Password at https://bitbucket.org/account/settings/app-passwords/"
        )

    return username, app_password


def _parse_bitbucket_remote() -> tuple[str, str]:
    """Parse the Bitbucket remote URL to extract workspace and repo slug.

    Returns:
        (workspace, repo_slug) tuple.

    Raises:
        RuntimeError: If the remote URL cannot be parsed.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError(f"Failed to get git remote URL: {exc}")

    url = result.stdout.strip()

    # Match patterns:
    #   https://bitbucket.org/workspace/repo.git
    #   git@bitbucket.org:workspace/repo.git
    #   https://username@bitbucket.org/workspace/repo.git
    patterns = [
        r"bitbucket\.org[:/]([^/]+)/([^/\s]+?)(?:\.git)?$",
        r"bitbucket\.org[:/]([^/]+)/([^/\s]+?)(?:\.git)?$",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            workspace = match.group(1)
            repo_slug = match.group(2)
            return workspace, repo_slug

    raise RuntimeError(
        f"Could not parse Bitbucket workspace and repo from remote URL: {url}"
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
        raise RuntimeError("`git` executable not found.")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Git command timed out: git {' '.join(args)}")

    if result.returncode != 0:
        # "nothing to commit" is non-fatal for commit
        if "nothing to commit" in result.stderr:
            return result
        raise RuntimeError(
            f"Git command failed (exit {result.returncode}): "
            f"git {' '.join(args)}\n{result.stderr.strip()}"
        )

    return result


class BitbucketProvider(GitProvider):
    """Git operations for Bitbucket Cloud via REST API v2.0.

    Bitbucket-specific patterns:
    - Uses "pull requests" (same terminology as GitHub).
    - PR URLs: https://bitbucket.org/workspace/repo/pull-requests/42
    - REST API base: https://api.bitbucket.org/2.0
    - Auth: Basic Auth with username + App Password.
    - No `gh`/`glab` equivalent — direct API calls.
    - Branch names: standard git conventions.
    - Default branch: typically 'main' (new repos) or 'master' (older repos).

    Usage:
        provider = BitbucketProvider()
        await provider.clone("git@bitbucket.org:org/repo.git", "./workdir")
        await provider.create_branch("feature/my-change")
        commit_hash = await provider.commit("feat: add feature")
        await provider.push()
        pr_url = await provider.create_pr("feat: add feature", "## Summary\\n...")
    """

    API_BASE = "https://api.bitbucket.org/2.0"

    def __init__(self) -> None:
        """Initialize the Bitbucket provider with API credentials."""
        self._username, self._app_password = _get_bitbucket_credentials()
        self._auth_header = self._build_auth_header()
        self._workspace: Optional[str] = None
        self._repo_slug: Optional[str] = None

    def _build_auth_header(self) -> str:
        """Build the Basic Auth header for Bitbucket API."""
        credentials = f"{self._username}:{self._app_password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _resolve_workspace_repo(self) -> tuple[str, str]:
        """Resolve and cache workspace + repo slug."""
        if self._workspace is None or self._repo_slug is None:
            self._workspace, self._repo_slug = _parse_bitbucket_remote()
        return self._workspace, self._repo_slug

    async def _api_request(
        self,
        method: str,
        path: str,
        json_data: Optional[dict] = None,
        timeout: int = 60,
    ) -> dict:
        """Make an authenticated request to the Bitbucket REST API.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path relative to API_BASE (e.g., '/repositories/ws/repo/pullrequests').
            json_data: Optional JSON body for POST/PUT requests.
            timeout: Request timeout in seconds.

        Returns:
            Parsed JSON response.

        Raises:
            RuntimeError: If the API request fails.
        """
        url = f"{self.API_BASE}{path}"
        headers = {
            "Authorization": self._auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(
                        url, headers=headers, json=json_data
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                if response.status_code >= 400:
                    error_detail = ""
                    try:
                        error_body = response.json()
                        error_detail = error_body.get("error", {}).get(
                            "message", response.text
                        )
                    except Exception:
                        error_detail = response.text

                    if response.status_code == 401:
                        raise RuntimeError(
                            "Bitbucket API authentication failed. "
                            "Check BITBUCKET_USERNAME and BITBUCKET_APP_PASSWORD."
                        )
                    if response.status_code == 403:
                        raise RuntimeError(
                            "Bitbucket API permission denied. "
                            "Ensure your App Password has 'Pull requests' Read & Write scope."
                        )
                    raise RuntimeError(
                        f"Bitbucket API error ({response.status_code}): {error_detail}"
                    )

                return response.json()

            except httpx.TimeoutException:
                raise RuntimeError(
                    f"Bitbucket API request timed out: {method} {url}"
                )
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    f"Bitbucket API connection failed: {exc}"
                )

    # ── GitProvider Interface ─────────────────────────────────────

    async def clone(self, url: str, path: str) -> None:
        """Clone a Bitbucket repository into the given path.

        Args:
            url: Repository URL (HTTPS or SSH).
            path: Local directory path to clone into.
        """
        parent = str(Path(path).parent)
        Path(parent).mkdir(parents=True, exist_ok=True)

        # If using HTTPS, embed credentials for clone
        if url.startswith("https://"):
            # Inject app password into HTTPS URL
            parsed = url.replace("https://", f"https://{quote(self._username)}:{quote(self._app_password)}@")
            url = parsed

        _run_git_sync(["clone", url, path], timeout=300)
        logger.info("Cloned %s → %s", url.replace(self._app_password, "***"), path)

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

        if "nothing to commit" in result.stderr:
            head = _run_git_sync(["rev-parse", "--short", "HEAD"], timeout=10)
            return head.stdout.strip()

        hash_result = _run_git_sync(["rev-parse", "--short", "HEAD"], timeout=10)
        commit_hash = hash_result.stdout.strip()
        logger.info("Committed: %s (%s)", message, commit_hash)
        return commit_hash

    async def push(self) -> None:
        """Push the current branch to the remote (origin).

        Raises:
            RuntimeError: If push fails.
        """
        branch_result = _run_git_sync(
            ["rev-parse", "--abbrev-ref", "HEAD"], timeout=10
        )
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
                    f"Check your Bitbucket credentials: {msg}"
                )
            if "protected branch" in msg.lower():
                raise RuntimeError(
                    f"Git push failed — branch '{branch}' is protected."
                )
            raise

        logger.info("Pushed branch: %s", branch)

    async def create_pr(self, title: str, body: str) -> str:
        """Create a pull request on Bitbucket via REST API.

        Args:
            title: PR title.
            body: PR description body (markdown).

        Returns:
            The PR URL (e.g., https://bitbucket.org/workspace/repo/pull-requests/42).

        Raises:
            RuntimeError: If PR creation fails.
        """
        workspace, repo_slug = self._resolve_workspace_repo()

        # Get current branch name
        branch_result = _run_git_sync(
            ["rev-parse", "--abbrev-ref", "HEAD"], timeout=10
        )
        source_branch = branch_result.stdout.strip()

        # Determine default branch
        try:
            default_result = _run_git_sync(
                ["symbolic-ref", "refs/remotes/origin/HEAD"],
                timeout=10,
            )
            default_branch = default_result.stdout.strip().replace(
                "refs/remotes/origin/", ""
            )
        except RuntimeError:
            default_branch = "main"  # Fallback

        pr_data = {
            "title": title,
            "description": body,
            "source": {
                "branch": {"name": source_branch},
            },
            "destination": {
                "branch": {"name": default_branch},
            },
        }

        path = f"/repositories/{workspace}/{repo_slug}/pullrequests"
        response = await self._api_request("POST", path, json_data=pr_data)

        # Extract PR URL
        pr_url = response.get("links", {}).get("html", {}).get("href", "")
        if not pr_url:
            pr_id = response.get("id", "unknown")
            pr_url = (
                f"https://bitbucket.org/{workspace}/{repo_slug}/pull-requests/{pr_id}"
            )

        logger.info("Created PR: %s", pr_url)
        return pr_url
