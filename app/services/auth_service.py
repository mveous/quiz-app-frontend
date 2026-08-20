import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_secure_token,
    hash_password,
    hash_refresh_token,
    hash_token,
    verify_password,
)
from app.models.user import User
from app.repositories.password_reset_token_repository import PasswordResetTokenRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.email_service import email_service


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)
        self._password_reset_tokens = PasswordResetTokenRepository(session)

    async def register(self, data: RegisterRequest) -> User:
        existing = await self._users.get_by_email(data.email)
        if existing is not None:
            raise ConflictError("An account with this email already exists")

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            country_code=data.country_code,
            locale=data.locale,
        )
        await self._users.create(user)
        await self._session.commit()
        return user

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self._users.get_by_email(data.email)
        if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")

        response = await self._issue_token_pair(user.id)
        await self._session.commit()
        return response

    async def refresh(self, raw_refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(raw_refresh_token, TokenType.REFRESH)
        except InvalidTokenError as exc:
            raise UnauthorizedError("Invalid or expired refresh token") from exc

        record = await self._refresh_tokens.get_valid_by_hash(hash_refresh_token(raw_refresh_token))
        if record is None:
            raise UnauthorizedError("Invalid or expired refresh token")

        # Rotate: revoke the used refresh token and issue a brand new pair.
        await self._refresh_tokens.revoke(record)
        response = await self._issue_token_pair(uuid.UUID(payload["sub"]))
        await self._session.commit()
        return response

    async def logout(self, raw_refresh_token: str) -> None:
        record = await self._refresh_tokens.get_valid_by_hash(hash_refresh_token(raw_refresh_token))
        if record is not None:
            await self._refresh_tokens.revoke(record)
            await self._session.commit()

    async def forgot_password(self, email: str) -> None:
        user = await self._users.get_by_email(email)
        if user is None or not user.is_active:
            # Never reveal whether an account exists for this email.
            return

        raw_token = generate_secure_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.password_reset_token_expire_minutes
        )
        await self._password_reset_tokens.create(user.id, hash_token(raw_token), expires_at)
        await self._session.commit()

        reset_url = f"{settings.frontend_origin}/reset-password?token={raw_token}"
        await email_service.send_password_reset_email(user.email, user.full_name, reset_url)

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        record = await self._password_reset_tokens.get_valid_by_hash(hash_token(raw_token))
        if record is None:
            raise UnauthorizedError("This reset link is invalid or has expired")

        user = await self._users.get_by_id(record.user_id)
        if user is None:
            raise UnauthorizedError("This reset link is invalid or has expired")

        user.password_hash = hash_password(new_password)
        await self._password_reset_tokens.mark_used(record)
        await self._refresh_tokens.revoke_all_for_user(user.id)
        await self._session.commit()

    async def _issue_token_pair(self, user_id: uuid.UUID) -> TokenResponse:
        access_token = create_access_token(user_id)
        raw_refresh_token, expires_at = create_refresh_token(user_id)
        await self._refresh_tokens.create(user_id, hash_refresh_token(raw_refresh_token), expires_at)
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )
