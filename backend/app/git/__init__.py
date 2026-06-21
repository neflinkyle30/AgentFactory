"""Git provider — abstractions for Git operations (clone, branch, commit, PR).

Provides:
- GitProvider ABC: base class for all Git operations
- GitHubProvider: via `gh` CLI
- GitLabProvider: via `glab` CLI + REST API
- BitbucketProvider: via Bitbucket REST API v2.0
- detect_provider(): auto-detect hosting provider from remote URL
- get_git_provider(): factory function returning the right provider
"""

from app.git.provider import GitProvider, detect_provider, get_git_provider
from app.git.github import GitHubProvider
from app.git.gitlab import GitLabProvider
from app.git.bitbucket import BitbucketProvider

__all__ = [
    "GitProvider",
    "GitHubProvider",
    "GitLabProvider",
    "BitbucketProvider",
    "detect_provider",
    "get_git_provider",
]
