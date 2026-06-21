"""Secret scanner — pre-push detection of sensitive data.

Scans the working directory for secrets before a PR push. Uses
regex-based detection for common secret patterns and optionally
integrates with `detect-secrets` tool if available.

Per PR-REQ-1: runs a secret scan on the git diff before pushing.
If secrets are detected, G8 fails and the push is blocked.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Regex patterns for common secret types ────────────────────────
# These patterns detect common secret formats. They are NOT exhaustive
# but catch the most common mistakes.

_SECRET_PATTERNS: list[tuple[str, str, str]] = [
    # (name, regex, description)
    (
        "aws_access_key",
        r"AKIA[0-9A-Z]{16}",
        "AWS Access Key ID",
    ),
    (
        "aws_secret_key",
        r"(?i)aws[_\s]*(secret|private)[_\s]*key[_\s]*[:=]\s*[\'\"][A-Za-z0-9\/+=]{40}",
        "AWS Secret Access Key",
    ),
    (
        "github_token",
        r"(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}",
        "GitHub Personal Access Token",
    ),
    (
        "gitlab_token",
        r"(glpat|gldt)-[A-Za-z0-9_\-]{20,}",
        "GitLab Personal Access Token",
    ),
    (
        "bitbucket_app_password",
        r"ATBB[A-Za-z0-9]{32}",
        "Bitbucket App Password",
    ),
    (
        "slack_token",
        r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[A-Za-z0-9_\-]+",
        "Slack Bot/User Token",
    ),
    (
        "google_api_key",
        r"AIza[0-9A-Za-z\-_]{35}",
        "Google API Key",
    ),
    (
        "jwt_token",
        r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",
        "JWT Token",
    ),
    (
        "private_key_header",
        r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        "Private Key (PEM format)",
    ),
    (
        "openai_key",
        r"sk-[A-Za-z0-9]{32,}",
        "OpenAI / DeepSeek API Key",
    ),
    (
        "generic_api_key",
        r"(?i)(api[_\s]*key|apikey|secret[_\s]*key|access[_\s]*key)[_\s]*[:=]\s*['\"][A-Za-z0-9_\-\.]{20,}['\"]",
        "Generic API Key / Secret in config",
    ),
    (
        "password_in_code",
        r"(?i)(password|passwd|pwd)[_\s]*[:=]\s*['\"][^'\"]{4,}['\"]",
        "Hardcoded Password",
    ),
    (
        "connection_string",
        r"(?i)(mongodb|postgres|mysql|redis|jdbc)[^:\s]*://[^@\s]+:[^@\s]+@",
        "Database Connection String with Credentials",
    ),
    (
        "stripe_key",
        r"(sk_live|pk_live|rk_live)_[A-Za-z0-9]{24,}",
        "Stripe Live Key",
    ),
]


@dataclass
class SecretFinding:
    """A single detected secret."""

    secret_type: str
    """Type of secret (e.g., 'aws_access_key')."""

    description: str
    """Human-readable description of the secret type."""

    file_path: str
    """Relative path to the file containing the secret."""

    line: int
    """Line number where the secret was found (1-indexed)."""

    match_preview: str
    """Preview of the matched text (truncated/redacted)."""


@dataclass
class SecretScanResult:
    """Result of a secret scan operation."""

    passed: bool
    """True if no secrets were detected."""

    findings: list[SecretFinding] = field(default_factory=list)
    """List of detected secrets (empty if passed)."""

    files_scanned: int = 0
    """Number of files scanned."""

    scan_method: str = "regex"
    """Method used: 'regex', 'detect-secrets', or 'none'."""

    def to_dict(self) -> dict:
        """Serialize to dict for artifact persistence."""
        return {
            "passed": self.passed,
            "findings": [
                {
                    "secret_type": f.secret_type,
                    "description": f.description,
                    "file_path": f.file_path,
                    "line": f.line,
                    # Never include match_preview in persisted output — it
                    # might contain partial secret text.
                }
                for f in self.findings
            ],
            "files_scanned": self.files_scanned,
            "scan_method": self.scan_method,
        }


class SecretScanner:
    """Scans files for secrets using regex patterns.

    Can optionally delegate to `detect-secrets` if installed, falling
    back to built-in regex patterns.

    Usage:
        scanner = SecretScanner()
        result = await scanner.scan_directory("/path/to/workdir")
        if not result.passed:
            for finding in result.findings:
                print(f"Secret found: {finding.secret_type} in {finding.file_path}")
    """

    # File extensions to scan (skip binary files)
    _TEXT_EXTENSIONS = frozenset({
        ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
        ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift",
        ".kt", ".scala", ".clj", ".ex", ".exs", ".erl", ".hs",
        ".sh", ".bash", ".zsh", ".fish",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
        ".xml", ".html", ".css", ".scss", ".less",
        ".md", ".txt", ".rst", ".env", ".envrc",
        ".tf", ".bicep", ".dockerfile", ".makefile",
    })

    # Directories to skip
    _SKIP_DIRS = frozenset({
        ".git", ".hg", ".svn",
        "node_modules", "vendor", ".venv", "venv",
        "__pycache__", ".pytest_cache", ".mypy_cache",
        "dist", "build", "target", "out",
        ".idea", ".vscode", ".DS_Store",
    })

    # Files to skip
    _SKIP_FILES = frozenset({
        "package-lock.json", "yarn.lock", "poetry.lock",
        "Cargo.lock", "go.sum", "Gemfile.lock",
    })

    def __init__(self, *, use_detect_secrets: bool = True) -> None:
        """Initialize the secret scanner.

        Args:
            use_detect_secrets: If True, try to use `detect-secrets` tool
                                before falling back to regex scanning.
        """
        self._use_detect_secrets = use_detect_secrets
        self._detect_secrets_available: Optional[bool] = None

    async def scan_directory(self, directory: str) -> SecretScanResult:
        """Scan a directory recursively for secrets.

        Args:
            directory: Path to the directory to scan (typically the cloned repo).

        Returns:
            SecretScanResult with pass/fail and findings.
        """
        # Try detect-secrets first if enabled
        if self._use_detect_secrets:
            ds_result = await self._scan_with_detect_secrets(directory)
            if ds_result is not None:
                return ds_result

        # Fall back to regex scanning
        return await self._scan_with_regex(directory)

    async def scan_diff(self, directory: str) -> SecretScanResult:
        """Scan only the git diff (staged + unstaged changes) for secrets.

        This is more efficient than scanning the entire directory and
        focuses on what would actually be pushed.

        Args:
            directory: Path to the git repository.

        Returns:
            SecretScanResult with pass/fail and findings.
        """
        # Try detect-secrets first
        if self._use_detect_secrets:
            ds_result = await self._scan_diff_with_detect_secrets(directory)
            if ds_result is not None:
                return ds_result

        # Fall back to regex on diff
        return await self._scan_diff_with_regex(directory)

    # ── detect-secrets integration ────────────────────────────────

    async def _check_detect_secrets(self) -> bool:
        """Check if detect-secrets is installed and available."""
        if self._detect_secrets_available is not None:
            return self._detect_secrets_available

        try:
            import asyncio

            process = await asyncio.create_subprocess_exec(
                "detect-secrets",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.communicate(), timeout=10)
            available = process.returncode == 0
        except Exception:
            available = False

        self._detect_secrets_available = available
        if not available:
            logger.info(
                "detect-secrets not available — using built-in regex scanner. "
                "Install with: pip install detect-secrets"
            )
        return available

    async def _scan_with_detect_secrets(
        self, directory: str
    ) -> Optional[SecretScanResult]:
        """Scan using detect-secrets tool. Returns None if not available."""
        if not await self._check_detect_secrets():
            return None

        try:
            import asyncio
            import json

            process = await asyncio.create_subprocess_exec(
                "detect-secrets",
                "scan",
                directory,
                "--all-files",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=120
            )

            if process.returncode != 0:
                logger.warning("detect-secrets scan failed: %s", stderr.decode())
                return None

            try:
                data = json.loads(stdout.decode())
            except json.JSONDecodeError:
                logger.warning("detect-secrets output was not valid JSON")
                return None

            findings = self._parse_detect_secrets_output(data)
            return SecretScanResult(
                passed=len(findings) == 0,
                findings=findings,
                files_scanned=0,
                scan_method="detect-secrets",
            )

        except Exception as exc:
            logger.warning("detect-secrets scan error: %s", exc)
            return None

    async def _scan_diff_with_detect_secrets(
        self, directory: str
    ) -> Optional[SecretScanResult]:
        """Scan git diff using detect-secrets."""
        if not await self._check_detect_secrets():
            return None

        try:
            import asyncio
            import json
            import subprocess as sync_sp

            # Get git diff
            diff_result = sync_sp.run(
                ["git", "diff", "--staged"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=directory,
            )
            if diff_result.returncode != 0:
                unstaged = sync_sp.run(
                    ["git", "diff"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=directory,
                )
                diff_text = unstaged.stdout
            else:
                diff_text = diff_result.stdout

            if not diff_text.strip():
                return SecretScanResult(
                    passed=True,
                    findings=[],
                    files_scanned=0,
                    scan_method="detect-secrets",
                )

            # Pipe diff to detect-secrets
            process = await asyncio.create_subprocess_exec(
                "detect-secrets",
                "scan",
                "--string", diff_text,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=60
            )

            if process.returncode != 0:
                return None

            try:
                data = json.loads(stdout.decode())
            except json.JSONDecodeError:
                return None

            findings = self._parse_detect_secrets_output(data)
            return SecretScanResult(
                passed=len(findings) == 0,
                findings=findings,
                files_scanned=0,
                scan_method="detect-secrets",
            )

        except Exception as exc:
            logger.warning("detect-secrets diff scan error: %s", exc)
            return None

    def _parse_detect_secrets_output(self, data: dict) -> list[SecretFinding]:
        """Parse detect-secrets JSON output into SecretFinding list."""
        findings: list[SecretFinding] = []
        results = data.get("results", {})

        for file_path, secrets in results.items():
            for secret in secrets:
                findings.append(
                    SecretFinding(
                        secret_type=secret.get("type", "unknown"),
                        description=secret.get("type", "Unknown secret"),
                        file_path=file_path,
                        line=secret.get("line_number", 0),
                        match_preview="[REDACTED — detect-secrets finding]",
                    )
                )

        return findings

    # ── Regex-based scanning ──────────────────────────────────────

    async def _scan_with_regex(self, directory: str) -> SecretScanResult:
        """Scan all text files in a directory using regex patterns."""
        findings: list[SecretFinding] = []
        files_scanned = 0
        root = Path(directory)

        if not root.exists():
            return SecretScanResult(
                passed=True,
                findings=[],
                files_scanned=0,
                scan_method="regex",
            )

        for file_path in root.rglob("*"):
            # Skip directories
            if file_path.is_dir():
                if file_path.name in self._SKIP_DIRS:
                    continue
                continue

            # Skip non-text files
            suffix = file_path.suffix.lower()
            if suffix not in self._TEXT_EXTENSIONS:
                continue

            # Skip lock files, etc.
            if file_path.name in self._SKIP_FILES:
                continue

            # Skip files that are too large (>1MB)
            try:
                if file_path.stat().st_size > 1_048_576:
                    continue
            except OSError:
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            files_scanned += 1
            relative_path = file_path.relative_to(root)

            for line_no, line in enumerate(content.splitlines(), start=1):
                for secret_name, pattern, description in _SECRET_PATTERNS:
                    match = re.search(pattern, line)
                    if match:
                        # Redact the matched text for safe logging
                        preview = match.group(0)
                        if len(preview) > 32:
                            preview = preview[:12] + "..." + preview[-8:]

                        findings.append(
                            SecretFinding(
                                secret_type=secret_name,
                                description=description,
                                file_path=str(relative_path),
                                line=line_no,
                                match_preview=preview,
                            )
                        )
                        # Only report first match per line
                        break

        passed = len(findings) == 0
        if not passed:
            logger.warning(
                "Secret scan found %d potential secrets in %d files",
                len(findings),
                files_scanned,
            )

        return SecretScanResult(
            passed=passed,
            findings=findings,
            files_scanned=files_scanned,
            scan_method="regex",
        )

    async def _scan_diff_with_regex(self, directory: str) -> SecretScanResult:
        """Scan only the git diff using regex patterns.

        This is more focused and faster than scanning all files.
        """
        import subprocess as sync_sp

        # Get combined staged + unstaged diff
        try:
            staged = sync_sp.run(
                ["git", "diff", "--staged", "--unified=0"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=directory,
            )
            unstaged = sync_sp.run(
                ["git", "diff", "--unified=0"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=directory,
            )
            diff_text = (staged.stdout or "") + "\n" + (unstaged.stdout or "")
        except (subprocess.CalledProcessError, FileNotFoundError):
            # If git is not available, fall back to full directory scan
            logger.warning("Git diff unavailable, falling back to full directory scan")
            return await self._scan_with_regex(directory)

        if not diff_text.strip():
            return SecretScanResult(
                passed=True,
                findings=[],
                files_scanned=0,
                scan_method="regex",
            )

        findings: list[SecretFinding] = []
        current_file = ""
        current_line_offset = 0

        for line in diff_text.splitlines():
            # Track file changes
            if line.startswith("diff --git"):
                current_file = line.split(" ")[2].lstrip("a/").lstrip("b/")
                current_line_offset = 0
                continue

            # Track line numbers from hunk headers
            if line.startswith("@@"):
                match = re.search(r"\+(\d+)", line)
                if match:
                    current_line_offset = int(match.group(1)) - 1
                continue

            # Only scan added/modified lines (start with +)
            if line.startswith("+") and not line.startswith("+++"):
                content = line[1:]  # Remove the + prefix
                current_line_offset += 1

                for secret_name, pattern, description in _SECRET_PATTERNS:
                    match = re.search(pattern, content)
                    if match:
                        preview = match.group(0)
                        if len(preview) > 32:
                            preview = preview[:12] + "..." + preview[-8:]

                        findings.append(
                            SecretFinding(
                                secret_type=secret_name,
                                description=description,
                                file_path=current_file,
                                line=current_line_offset,
                                match_preview=preview,
                            )
                        )
                        break

        passed = len(findings) == 0
        return SecretScanResult(
            passed=passed,
            findings=findings,
            files_scanned=0,
            scan_method="regex",
        )


# ── Convenience function ──────────────────────────────────────────


async def scan_for_secrets(
    directory: str,
    *,
    diff_only: bool = True,
    use_detect_secrets: bool = True,
) -> SecretScanResult:
    """Convenience function: scan a directory for secrets.

    Args:
        directory: Path to scan (git repo root).
        diff_only: If True, only scan git diff (faster, more relevant).
        use_detect_secrets: If True, try detect-secrets tool first.

    Returns:
        SecretScanResult with pass/fail verdict and findings.
    """
    scanner = SecretScanner(use_detect_secrets=use_detect_secrets)

    if diff_only:
        return await scanner.scan_diff(directory)
    else:
        return await scanner.scan_directory(directory)
