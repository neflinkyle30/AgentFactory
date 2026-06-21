"""JWT token creation, verification, and password hashing.

Uses python-jose for JWT and passlib for bcrypt password hashing.
Token configuration is read from app.config.settings.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# ── Password hashing ────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt.

    Args:
        password: The plaintext password to hash.

    Returns:
        The bcrypt hash string (includes salt).
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        plain_password: The password to check.
        hashed_password: The stored bcrypt hash.

    Returns:
        True if the password matches the hash.
    """
    return _pwd_context.verify(plain_password, hashed_password)


# ── JWT Token creation ──────────────────────────────────────────────


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    team_id: str,
    *,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token.

    Args:
        user_id: The user's UUID (as string).
        email: The user's email address.
        role: The user's role (admin, developer, viewer).
        team_id: The user's team UUID (as string).
        expires_delta: Custom expiration. Defaults to config setting.

    Returns:
        Encoded JWT string.
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "team_id": team_id,
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: str,
    *,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token.

    Args:
        user_id: The user's UUID (as string).
        expires_delta: Custom expiration. Defaults to config setting.

    Returns:
        Encoded JWT string.
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ── JWT Verification ────────────────────────────────────────────────


class TokenPayload:
    """Decoded JWT token payload with convenience accessors."""

    def __init__(self, claims: Dict[str, Any]) -> None:
        self._claims = claims

    @property
    def user_id(self) -> str:
        return self._claims.get("sub", "")

    @property
    def email(self) -> str:
        return self._claims.get("email", "")

    @property
    def role(self) -> str:
        return self._claims.get("role", "developer")

    @property
    def team_id(self) -> str:
        return self._claims.get("team_id", "")

    @property
    def token_type(self) -> str:
        return self._claims.get("type", "access")

    @property
    def claims(self) -> Dict[str, Any]:
        return dict(self._claims)


def decode_token(token: str) -> Optional[TokenPayload]:
    """Decode and validate a JWT token.

    Args:
        token: The JWT string to decode.

    Returns:
        TokenPayload if valid, None if expired or invalid.
    """
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(claims)
    except JWTError:
        return None


def verify_access_token(token: str) -> Optional[TokenPayload]:
    """Verify an access token (type=access).

    Args:
        token: The JWT access token.

    Returns:
        TokenPayload if valid access token, None otherwise.
    """
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.token_type != "access":
        return None
    return payload


def verify_refresh_token(token: str) -> Optional[TokenPayload]:
    """Verify a refresh token (type=refresh).

    Args:
        token: The JWT refresh token.

    Returns:
        TokenPayload if valid refresh token, None otherwise.
    """
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.token_type != "refresh":
        return None
    return payload
