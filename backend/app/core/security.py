import hashlib
import secrets
from datetime import timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException

from app.core.config import Settings
from app.models.auth import utcnow

password_hasher = PasswordHasher()


def hash_password(password: str):
    return password_hasher.hash(password)


def verify_password(encoded: str, password: str):
    try:
        return password_hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def new_refresh_token():
    return secrets.token_urlsafe(48)


def token_hash(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: UUID, session_id: UUID, settings: Settings):
    now = utcnow()
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": str(session_id),
            "iss": settings.jwt_issuer,
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode_access_token(token: str, settings: Settings):
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "sid", "iss", "iat", "exp"]},
        )
        return UUID(claims["sub"]), UUID(claims["sid"])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, "Invalid or expired session") from None
