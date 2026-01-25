import asyncio
import os
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.append(str(Path(__file__).parents[1] / "src"))

from app.db.session import get_db
from app.main import app

ENV_TEST_PATH = Path(__file__).parents[1] / ".env.test"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


_load_env_file(ENV_TEST_PATH)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://cc_user:cc_password@localhost:5433/cc_rewards_test",
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="function")
async def setup_database():
    """Create tables for tests that need the database, and drop them after.

    This fixture is intentionally NOT autouse so pure unit tests (e.g. parsers)
    can run without requiring a local Postgres instance.
    """
    from app.models.base import BaseModel
    
    async with test_engine.begin() as conn:
        # Create all tables
        await conn.run_sync(BaseModel.metadata.create_all)
    
    yield
    
    async with test_engine.begin() as conn:
        # Drop all tables after tests
        await conn.run_sync(BaseModel.metadata.drop_all)
    
    # Dispose of all connections in the pool to prevent asyncpg connection reuse issues
    await test_engine.dispose()


@pytest.fixture
async def db_session(setup_database):
    """Provide test database session with fresh connection per test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user for authentication tests."""
    from app.core.security import hash_password
    from app.models.user import User
    from app.repositories.user import UserRepository
    
    repo = UserRepository(db_session)
    user = User(
        email="testuser@example.com",
        password_hash=hash_password("password123"),
        full_name="Test User",
    )
    created_user = await repo.create(user)
    return created_user


@pytest.fixture
async def auth_headers(test_user):
    """Provide authentication headers with valid JWT token."""
    from app.core.security import create_access_token
    
    token = create_access_token(user_id=test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client(db_session: AsyncSession):
    """Provide test client with database override."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()
