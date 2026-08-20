import uuid

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def list_users(
        self, limit: int, offset: int, search: str | None = None
    ) -> tuple[list[User], int]:
        users = await self._users.list_paginated(limit, offset, search)
        total = await self._users.count(search)
        return users, total

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def update_role(self, acting_admin: User, user_id: uuid.UUID, role: UserRole) -> User:
        if acting_admin.id == user_id and role != UserRole.ADMIN:
            raise ValidationFailedError("You cannot remove your own admin role")

        user = await self.get_user(user_id)
        user.role = role
        await self._session.commit()
        return user

    async def update_active_status(
        self, acting_admin: User, user_id: uuid.UUID, is_active: bool
    ) -> User:
        if acting_admin.id == user_id and not is_active:
            raise ValidationFailedError("You cannot deactivate your own account")

        user = await self.get_user(user_id)
        user.is_active = is_active
        await self._session.commit()
        return user

    async def get_system_health(self) -> dict:
        database_ok = await self._check_database()
        redis_ok = await self._check_redis()
        return {
            "database": database_ok,
            "redis": redis_ok,
            "ai_provider": settings.ai_provider,
        }

    async def _check_database(self) -> bool:
        try:
            await self._session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def _check_redis(self) -> bool:
        client = redis.from_url(settings.redis_url)
        try:
            return bool(await client.ping())
        except Exception:
            return False
        finally:
            await client.aclose()
