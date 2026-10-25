"""Pytest fixtures for TLEX tests."""

import asyncio
import os
from collections.abc import AsyncGenerator

# Before app imports (settings are cached): the auth tests register several users
os.environ.setdefault("ENABLE_REGISTRATION", "true")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app
from app.api.deps import get_db
from app.core.rate_limit import limiter

# The limiter stores its counters in Redis; tests run against in-memory SQLite only
limiter.enabled = False


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    
    async def override_get_db():
        yield test_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_session: AsyncSession) -> dict:
    """Create authenticated user and return auth headers."""
    from app.models.user import User
    from app.core.security import hash_password, create_access_token
    
    # Create test user
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpass123"),
        is_admin=False,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    
    # Create token
    token = create_access_token(data={"sub": str(user.id)})
    
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, test_session: AsyncSession) -> dict:
    """Create admin user and return auth headers."""
    from app.models.user import User
    from app.core.security import hash_password, create_access_token
    
    # Create admin user
    user = User(
        email="admin@example.com",
        password_hash=hash_password("adminpass123"),
        is_admin=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    
    # Create token
    token = create_access_token(data={"sub": str(user.id)})
    
    return {"Authorization": f"Bearer {token}"}
