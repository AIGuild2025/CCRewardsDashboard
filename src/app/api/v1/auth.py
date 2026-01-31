"""Authentication endpoints for user registration, login, and token management."""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service, get_current_user
from app.models.user import User
from app.schemas.auth import (
    CurrentUser,
    LoginRequest,
    RefreshRequest,
    TokenPair,
    UserRegister,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account with email and password.",
)
async def register(
    data: UserRegister,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """
    Register a new user account.

    Args:
        data: Registration data (email, password, full_name)
        auth_service: Authentication service

    Returns:
        Created user data (without password)

    Raises:
        400: Email already registered
        422: Validation error
    """
    user = await auth_service.register(
        email=data.email,
        password=data.password,
        full_name=data.full_name,
    )
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="User login",
    description="Authenticate with email and password to receive JWT tokens.",
)
async def login(
    data: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    """
    Authenticate user and return JWT tokens.

    Args:
        data: Login credentials (email, password)
        auth_service: Authentication service

    Returns:
        Access token (30 min) and refresh token (7 days)

    Raises:
        401: Invalid credentials
        403: User account deactivated
    """
    token_pair = await auth_service.login(
        email=data.email,
        password=data.password,
    )
    return token_pair


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Refresh access token",
    description="Get new token pair using a valid refresh token.",
)
async def refresh(
    data: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    """
    Generate new token pair using refresh token.

    Args:
        data: Refresh token
        auth_service: Authentication service

    Returns:
        New access token and refresh token

    Raises:
        401: Invalid or expired refresh token
        403: User account deactivated
    """
    token_pair = await auth_service.refresh_tokens(data.refresh_token)
    return token_pair


@router.get(
    "/me",
    response_model=CurrentUser,
    summary="Get current user",
    description="Get authenticated user's profile information.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> CurrentUser:
    """
    Get current authenticated user's profile.

    Args:
        current_user: Authenticated user from JWT token

    Returns:
        User profile data

    Raises:
        401: Invalid or missing authorization token
        403: User account deactivated
    """
    return CurrentUser.model_validate(current_user)
