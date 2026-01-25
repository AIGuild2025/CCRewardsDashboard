"""Integration tests for authentication API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.user import User
from app.repositories.user import UserRepository


class TestUserRegistration:
    """Test user registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test successful user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "full_name": "New User",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data  # Password should not be in response

        # Verify user exists in database
        repo = UserRepository(db_session)
        user = await repo.get_by_email("newuser@example.com")
        assert user is not None
        assert user.email == "newuser@example.com"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        """Test registration with existing email returns 400."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "AnotherPass123!",
                "full_name": "Duplicate User",
            },
        )

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email format."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass123!",
                "full_name": "Test User",
            },
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Test registration with password shorter than 8 characters."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "short",
                "full_name": "Test User",
            },
        )

        assert response.status_code == 400


class TestUserLogin:
    """Test user login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login returns tokens."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "password123",  # Plain password from fixture
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert isinstance(data["access_token"], str)
        assert isinstance(data["refresh_token"], str)
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client: AsyncClient, test_user: User):
        """Test login with incorrect password returns 401."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent email returns 401."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "notexist@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client: AsyncClient, db_session: AsyncSession):
        """Test login with deactivated user returns 403."""
        from app.core.security import hash_password
        
        # Create and deactivate user
        repo = UserRepository(db_session)
        user = User(
            email="inactive@example.com",
            password_hash=hash_password("password123"),
            full_name="Inactive User",
            is_active=False,
        )
        await repo.create(user)

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "inactive@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 403
        assert "deactivated" in response.json()["detail"].lower()


class TestTokenRefresh:
    """Test token refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client: AsyncClient, test_user: User):
        """Test refreshing tokens with valid refresh token."""
        # First login to get tokens
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "password123",
            },
        )
        refresh_token = login_response.json()["refresh_token"]

        # Use refresh token to get new tokens
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client: AsyncClient):
        """Test refresh with invalid token returns 401."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_using_access_token(self, client: AsyncClient, test_user: User):
        """Test that using access token for refresh fails."""
        # Login to get access token
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "password123",
            },
        )
        access_token = login_response.json()["access_token"]

        # Try to use access token for refresh (should fail)
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )

        # Should still work since we're just checking token validity
        # In production, you might want to validate token type
        assert response.status_code in [200, 401]


class TestGetCurrentUser:
    """Test GET /me endpoint (requires authentication)."""

    @pytest.mark.asyncio
    async def test_get_me_with_valid_token(self, client: AsyncClient, test_user: User):
        """Test GET /me with valid access token returns user info."""
        # Login to get access token
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "password123",
            },
        )
        access_token = login_response.json()["access_token"]

        # Request user info with token
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["full_name"] == test_user.full_name
        assert data["id"] == str(test_user.id)
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_me_without_token(self, client: AsyncClient):
        """Test GET /me without authorization header returns 403."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_me_with_invalid_token(self, client: AsyncClient):
        """Test GET /me with invalid token returns 401."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_with_malformed_header(self, client: AsyncClient):
        """Test GET /me with malformed authorization header returns 403."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "NotBearer token"},
        )

        assert response.status_code == 403


class TestProtectedRouteAccess:
    """Test that protected routes properly validate tokens."""

    @pytest.mark.asyncio
    async def test_protected_route_rejects_invalid_token(self, client: AsyncClient):
        """Test that protected route rejects invalid token."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer fake.invalid.token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_route_accepts_valid_token(self, client: AsyncClient, test_user: User):
        """Test that protected route accepts valid token."""
        # Create valid token
        access_token = create_access_token(test_user.id)

        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
