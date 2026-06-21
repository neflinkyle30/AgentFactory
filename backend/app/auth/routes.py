"""Authentication routes — register, login, and user profile."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.jwt import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_refresh_token,
)
from app.database import get_db
from app.models import User, Team
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── POST /api/auth/register ─────────────────────────────────────────


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user account and return JWT tokens.

    Creates a new team (or uses existing if team_name matches),
    creates the user with a hashed password, and returns access
    and refresh tokens.
    """
    # Check if email already exists
    stmt = select(User).where(User.email == body.email)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Find or create team
    stmt = select(Team).where(Team.name == body.team_name)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if team is None:
        team = Team(id=uuid4(), name=body.team_name)
        db.add(team)
        await db.flush()

    # Create user
    user = User(
        id=uuid4(),
        email=body.email,
        password_hash=hash_password(body.password),
        role="developer",
        team_id=team.id,
    )
    db.add(user)
    await db.flush()

    # Generate tokens
    access_token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        team_id=str(user.team_id),
    )
    refresh_token = create_refresh_token(user_id=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ── POST /api/auth/login ────────────────────────────────────────────


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate a user and return JWT tokens.

    Verifies email and password, then issues access and refresh tokens.
    """
    # Find user by email
    stmt = select(User).where(User.email == body.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Generate tokens
    access_token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        team_id=str(user.team_id),
    )
    refresh_token = create_refresh_token(user_id=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ── GET /api/auth/me ────────────────────────────────────────────────


@router.get("/me", response_model=MeResponse)
async def get_me(
    user: User = Depends(get_current_user),
) -> MeResponse:
    """Return the current authenticated user's profile.

    Requires a valid Bearer token in the Authorization header.
    """
    return MeResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            team_id=user.team_id,
        )
    )


# ── POST /api/auth/refresh ──────────────────────────────────────────


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Refresh an access token using a valid refresh token.

    Request body: {"refresh_token": "..."}
    """
    refresh_token_str = body.get("refresh_token")
    if not refresh_token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing refresh_token in request body",
        )

    # Verify refresh token
    payload = verify_refresh_token(refresh_token_str)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Load user
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

    # Issue new tokens (rotate refresh token)
    access_token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        team_id=str(user.team_id),
    )
    new_refresh_token = create_refresh_token(user_id=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )
