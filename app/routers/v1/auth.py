from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.responses import APIResponse, success_response
from app.database.session import get_db
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import limiter
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=APIResponse[UserOut],
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(f"{settings.rate_limit_auth_per_minute}/minute")
async def register(
    request: Request, data: RegisterRequest, session: AsyncSession = Depends(get_db)
) -> dict:
    user = await AuthService(session).register(data)
    return success_response(UserOut.model_validate(user), "Account created")


@router.post("/login", response_model=APIResponse[TokenResponse])
@limiter.limit(f"{settings.rate_limit_auth_per_minute}/minute")
async def login(
    request: Request, data: LoginRequest, session: AsyncSession = Depends(get_db)
) -> dict:
    tokens = await AuthService(session).login(data)
    return success_response(tokens, "Logged in")


@router.post("/refresh", response_model=APIResponse[TokenResponse])
@limiter.limit(f"{settings.rate_limit_auth_per_minute}/minute")
async def refresh(
    request: Request, data: RefreshRequest, session: AsyncSession = Depends(get_db)
) -> dict:
    tokens = await AuthService(session).refresh(data.refresh_token)
    return success_response(tokens, "Token refreshed")


@router.post("/logout", response_model=APIResponse[None])
async def logout(data: RefreshRequest, session: AsyncSession = Depends(get_db)) -> dict:
    await AuthService(session).logout(data.refresh_token)
    return success_response(None, "Logged out")


@router.get("/me", response_model=APIResponse[UserOut])
async def me(current_user: User = Depends(get_current_user)) -> dict:
    return success_response(UserOut.model_validate(current_user), "")


@router.post("/forgot-password", response_model=APIResponse[None])
@limiter.limit(f"{settings.rate_limit_auth_per_minute}/minute")
async def forgot_password(
    request: Request, data: ForgotPasswordRequest, session: AsyncSession = Depends(get_db)
) -> dict:
    await AuthService(session).forgot_password(data.email)
    return success_response(None, "If an account exists for that email, a reset link has been sent")


@router.post("/reset-password", response_model=APIResponse[None])
@limiter.limit(f"{settings.rate_limit_auth_per_minute}/minute")
async def reset_password(
    request: Request, data: ResetPasswordRequest, session: AsyncSession = Depends(get_db)
) -> dict:
    await AuthService(session).reset_password(data.token, data.new_password)
    return success_response(None, "Password reset — sign in with your new password")
