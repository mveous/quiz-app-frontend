import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user

    async def list_paginated(
        self, limit: int, offset: int, search: str | None = None
    ) -> list[User]:
        query = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        query = self._apply_search(query, search)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count(self, search: str | None = None) -> int:
        query = select(func.count()).select_from(User)
        query = self._apply_search(query, search)
        result = await self._session.execute(query)
        return result.scalar_one()

    @staticmethod
    def _apply_search(query, search: str | None):
        if not search:
            return query
        pattern = f"%{search}%"
        return query.where(or_(User.email.ilike(pattern), User.full_name.ilike(pattern)))
