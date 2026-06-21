"""Pydantic schemas for authentication endpoints."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request to create a new user account."""

    email: str = Field(..., min_length=5, max_length=320, description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")
    team_name: str = Field(
        default="default", min_length=1, max_length=255, description="Team name"
    )


class LoginRequest(BaseModel):
    """Request to authenticate and receive JWT tokens."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    """JWT token pair returned on login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user profile returned by /api/auth/me."""

    id: UUID
    email: str
    role: str
    team_id: UUID


class MeResponse(BaseModel):
    """Response for /api/auth/me — includes user profile."""

    user: UserResponse
