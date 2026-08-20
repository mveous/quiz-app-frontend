import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import APIResponse, success_response
from app.database.session import get_db
from app.middleware.auth import require_admin
from app.models.user import User
from app.schemas.admin import (
    AdminUserListOut,
    AdminUserOut,
    SystemHealthOut,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
)
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=APIResponse[AdminUserListOut])
async def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, max_length=200),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    users, total = await AdminService(session).list_users(limit, offset, search)
    return success_response(
        AdminUserListOut(
            items=[AdminUserOut.model_validate(u) for u in users],
            total=total,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/users/{user_id}", response_model=APIResponse[AdminUserOut])
async def get_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    user = await AdminService(session).get_user(user_id)
    return success_response(AdminUserOut.model_validate(user))


@router.patch("/users/{user_id}/role", response_model=APIResponse[AdminUserOut])
async def update_user_role(
    user_id: uuid.UUID,
    data: UpdateUserRoleRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    user = await AdminService(session).update_role(current_user, user_id, data.role)
    return success_response(AdminUserOut.model_validate(user), "User role updated")


@router.patch("/users/{user_id}/status", response_model=APIResponse[AdminUserOut])
async def update_user_status(
    user_id: uuid.UUID,
    data: UpdateUserStatusRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    user = await AdminService(session).update_active_status(
        current_user, user_id, data.is_active
    )
    return success_response(AdminUserOut.model_validate(user), "User status updated")


@router.get("/system-health", response_model=APIResponse[SystemHealthOut])
async def system_health(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    health = await AdminService(session).get_system_health()
    return success_response(SystemHealthOut(**health))
