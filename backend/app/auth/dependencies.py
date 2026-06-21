"""FastAPI dependencies for authentication.

Provides get_current_user — a FastAPI dependency that extracts
and validates the JWT Bearer token from the Authorization header,
loads the user from the database, and returns the User model.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import verify_access_token, TokenPayload
from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

# ── Security scheme ─────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


# ── get_current_user ────────────────────────────────────────────────


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: authenticate the current user from JWT.

    Extracts the Bearer token from the Authorization header, validates
    it, loads the user from the database, and returns the User model.

    Raises:
        HTTPException 401: If no token, invalid token, or user not found.

    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": str(user.id)}
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = verify_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load user from database
    try:
        user_id = UUID(payload.user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


# ── Optional user (for endpoints that work with and without auth) ───


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """FastAPI dependency: optionally authenticate the current user.

    Returns None if no token is provided, otherwise behaves like
    get_current_user.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    payload = verify_access_token(token)
    if payload is None:
        return None

    try:
        user_id = UUID(payload.user_id)
    except ValueError:
        return None

    return await db.get(User, user_id)
