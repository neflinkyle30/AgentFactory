"""Guards — safety checks and pre-push validations.

Guards run before critical operations (push, PR creation) to enforce
safety policies. Each guard is a self-contained check that returns
a pass/fail verdict with findings.
"""

from app.guards.secret_scan import SecretScanner, SecretScanResult, scan_for_secrets

__all__ = ["SecretScanner", "SecretScanResult", "scan_for_secrets"]
