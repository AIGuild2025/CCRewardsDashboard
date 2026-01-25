"""Authentication service with business logic."""

from uuid import UUID

from fastapi import HTTPException, status

from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_user_id_from_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenPair


class AuthService:
    """Service for authentication operations."""

    def __init__(self, user_repo: UserRepository):
        """
        Initialize authentication service.

        Args:
            user_repo: User repository for database operations
        """
        self.user_repo = user_repo

    async def register(self, email: str, password: str, full_name: str) -> User:
        """
        Register a new user.

        Args:
            email: User email address
            password: Plain text password
            full_name: User's full name

        Returns:
            Created user object

        Raises:
            HTTPException: If email already exists
        """
        # Check if email already exists
        if await self.user_repo.email_exists(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Hash password
        hashed_password = hash_password(password)

        # Create user
        user = User(
            email=email,
            password_hash=hashed_password,
            full_name=full_name,
        )

        created_user = await self.user_repo.create(user)
        return created_user

    async def login(self, email: str, password: str) -> TokenPair:
        """
        Authenticate user and return JWT tokens.

        Args:
            email: User email address
            password: Plain text password

        Returns:
            Token pair (access + refresh tokens)

        Raises:
            HTTPException: If credentials are invalid
        """
        # Find user by email
        user = await self.user_repo.get_by_email(email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        # Verify password
        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated",
            )

        # Create tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """
        Generate new token pair using refresh token.

        Args:
            refresh_token: Valid JWT refresh token

        Returns:
            New token pair (access + refresh tokens)

        Raises:
            HTTPException: If refresh token is invalid
        """
        try:
            # Decode token and extract user ID
            user_id = get_user_id_from_token(refresh_token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        # Verify user still exists and is active
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated",
            )

        # Create new token pair
        access_token = create_access_token(user.id)
        new_refresh_token = create_refresh_token(user.id)

        return TokenPair(
            access_token=access_token,
            refresh_token=new_refresh_token,
        )

    async def get_current_user(self, user_id: UUID) -> User:
        """
        Get user by ID for authenticated requests.

        Args:
            user_id: User ID from JWT token

        Returns:
            User object

        Raises:
            HTTPException: If user not found or inactive
        """
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated",
            )

        return user
