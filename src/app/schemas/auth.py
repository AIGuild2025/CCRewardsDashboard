"""Pydantic schemas for authentication endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    """Request model for user registration."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    full_name: str = Field(..., min_length=1, max_length=255, description="User's full name")


class LoginRequest(BaseModel):
    """Request model for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenPair(BaseModel):
    """Response model for authentication tokens."""

    access_token: str = Field(..., description="JWT access token (30 min)")
    refresh_token: str = Field(..., description="JWT refresh token (7 days)")
    token_type: str = Field(default="bearer", description="Token type")


class RefreshRequest(BaseModel):
    """Request model for token refresh."""

    refresh_token: str = Field(..., description="JWT refresh token")


class UserResponse(BaseModel):
    """Response model for user data (without sensitive fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime


class CurrentUser(BaseModel):
    """Response model for current authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    is_active: bool
