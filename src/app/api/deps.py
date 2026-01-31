"""FastAPI dependency injection for authentication and database."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_user_id_from_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.auth import AuthService

# OAuth2 bearer token scheme
security = HTTPBearer()


async def get_user_repository(
    db: AsyncSession = Depends(get_db),
) -> UserRepository:
    """
    Get user repository instance.

    Args:
        db: Database session

    Returns:
        UserRepository instance
    """
    return UserRepository(db)


async def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthService:
    """
    Get authentication service instance.

    Args:
        user_repo: User repository

    Returns:
        AuthService instance
    """
    return AuthService(user_repo)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    user_repo: UserRepository = Depends(get_user_repository),
) -> User:
    """
    Extract and validate user from JWT token.

    Args:
        credentials: HTTP bearer token credentials
        user_repo: User repository for database queries

    Returns:
        Authenticated user object

    Raises:
        HTTPException: If token is invalid, expired, or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Extract token from credentials
        token = credentials.credentials

        # Decode token and extract user ID
        user_id = get_user_id_from_token(token)

    except JWTError:
        raise credentials_exception
    except ValueError:
        raise credentials_exception

    # Get user from database
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise credentials_exception

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user
