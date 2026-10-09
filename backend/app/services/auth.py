from datetime import timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    new_refresh_token,
    token_hash,
    verify_password,
)
from app.models.auth import RefreshToken, User, utcnow
from app.repositories.auth import AuthRepository
from app.schemas.auth import TokenResponse, UserResponse
from app.services.analytics import AnalyticsService


def is_valid_session(record):
    return (
        record is not None
        and record.revoked_at is None
        and (record.expires_at.replace(tzinfo=timezone.utc) > utcnow())
    )


class AuthService:
    def __init__(self, repository: AuthRepository, settings: Settings):
        self.repository = repository
        self.settings = settings

    async def issue_tokens(self, user):
        raw = new_refresh_token()
        session = RefreshToken(
            user_id=user.id,
            token_hash=token_hash(raw),
            expires_at=utcnow() + timedelta(days=self.settings.refresh_token_days),
        )
        await self.repository.add(session)
        return TokenResponse(
            access_token=create_access_token(user.id, session.id, self.settings),
            refresh_token=raw,
            expires_in=self.settings.access_token_minutes * 60,
            user=UserResponse.model_validate(user),
        )

    async def register(self, credentials):
        user = User(
            email=str(credentials.email),
            password_hash=await run_in_threadpool(
                hash_password, credentials.password.get_secret_value()
            ),
        )
        try:
            await self.repository.add(user)
            result = await self.issue_tokens(user)
            AnalyticsService(self.repository.session).record("registration_completed", user.id)
            await self.repository.commit()
            return result
        except IntegrityError:
            await self.repository.rollback()
            raise HTTPException(409, "An account with this email already exists") from None

    async def login(self, credentials):
        user = await self.repository.user_by_email(str(credentials.email))
        if user is None:
            # Keep failed password work comparable for unknown and known accounts.
            await run_in_threadpool(hash_password, credentials.password.get_secret_value())
            raise HTTPException(401, "Invalid email or password")
        valid = await run_in_threadpool(
            verify_password, user.password_hash, credentials.password.get_secret_value()
        )
        if not valid or not user.is_active:
            raise HTTPException(401, "Invalid email or password")
        result = await self.issue_tokens(user)
        await self.repository.commit()
        return result

    async def refresh(self, raw):
        session = await self.repository.refresh_by_hash(token_hash(raw))
        if not is_valid_session(session):
            raise HTTPException(401, "Invalid or expired session")
        user = await self.repository.user_by_id(session.user_id)
        if user is None or not user.is_active:
            raise HTTPException(401, "Invalid or expired session")
        session.revoked_at = utcnow()
        result = await self.issue_tokens(user)
        await self.repository.commit()
        return result

    async def logout(self, raw):
        session = await self.repository.refresh_by_hash(token_hash(raw))
        if session is not None and session.revoked_at is None:
            session.revoked_at = utcnow()
            await self.repository.commit()

    async def current_user(self, token):
        user_id, session_id = decode_access_token(token, self.settings)
        session = await self.repository.session_by_id(session_id)
        if not is_valid_session(session) or session.user_id != user_id:
            raise HTTPException(401, "Invalid or expired session")
        user = await self.repository.user_by_id(user_id)
        if user is None or not user.is_active:
            raise HTTPException(401, "Invalid or expired session")
        return user
