import os

# Must be set before any `app.*` module is imported, since app.core.config
# reads them once at import time into a module-level settings singleton.
os.environ["AI_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://mveousquiz:change-me-locally@localhost:5433/mveousquiz_test"
)
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["REDIS_URL"] = "redis://localhost:6380/0"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6380/0"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6380/1"
# High limits: the in-memory rate limiter persists for the whole test session,
# and dozens of tests hitting these endpoints would otherwise trip production limits.
os.environ["RATE_LIMIT_AUTH_PER_MINUTE"] = "1000"
os.environ["RATE_LIMIT_AI_GENERATION_PER_MINUTE"] = "1000"
os.environ["RATE_LIMIT_DOCUMENT_UPLOAD_PER_MINUTE"] = "1000"
# Keep the suite hermetic: no test should make a real network call to Wikipedia.
# Tests that need to verify web-search wiring monkeypatch WebSearchService directly.
os.environ["WEB_SEARCH_ENABLED"] = "false"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.database.base import Base  # noqa: E402
from app.database.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import *  # noqa: E402,F401,F403
from app.models.enums import UserRole  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _prepare_database():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def registered_user(client):
    """Registers and logs in a fresh user; returns (bearer_headers, tokens_dict)."""

    async def _create(email: str = "student@example.com", password: str = "Str0ngPassw0rd!"):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": "Test Student",
                "country_code": "IN",
            },
        )
        response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        tokens = response.json()["data"]
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        return headers, tokens

    return _create


@pytest_asyncio.fixture
async def admin_user(registered_user):
    """Registers/logs in a fresh user then flips their role to admin directly
    in the DB (the register endpoint never accepts a role — see
    scripts/promote_admin.py). Returns (headers, tokens)."""

    async def _create(email: str = "admin@example.com", password: str = "Str0ngPassw0rd!"):
        headers, tokens = await registered_user(email, password)
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            user.role = UserRole.ADMIN
            await session.commit()
        return headers, tokens

    return _create
