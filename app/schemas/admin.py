import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    country_code: str | None
    locale: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int
    limit: int
    offset: int


class UpdateUserRoleRequest(BaseModel):
    role: UserRole


class UpdateUserStatusRequest(BaseModel):
    is_active: bool


class SystemHealthOut(BaseModel):
    database: bool
    redis: bool
    ai_provider: str
