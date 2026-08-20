from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Used by the request-serving app, which runs one long-lived event loop for the
# whole process — pooling connections across requests is safe and desirable here.
engine = create_async_engine(settings.database_url, pool_pre_ping=True, future=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, autoflush=False, autocommit=False
)

# Used by Celery tasks, each of which runs its own short-lived `asyncio.run()` event
# loop. A pooled connection checked out under one task's loop is invalid once that
# loop closes, so task code gets its own NullPool engine: every checkout opens a
# fresh physical connection and closes it before the loop tears down.
task_engine = create_async_engine(settings.database_url, poolclass=NullPool, future=True)

TaskSessionLocal = async_sessionmaker(
    bind=task_engine, expire_on_commit=False, autoflush=False, autocommit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
