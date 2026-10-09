from __future__ import annotations

import json
import re
from typing import Any

from fastapi import Depends, HTTPException, Request
from workers import fetch

from core import env_value, first, now, run


EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _auth_config(request: Request) -> tuple[str, str]:
    return (
        env_value(request, "SUPABASE_URL").rstrip("/"),
        env_value(request, "SUPABASE_ANON_KEY"),
    )


async def _json(response) -> dict[str, Any]:
    try:
        value = await response.json()
        return dict(value)
    except Exception:
        return {}


async def _supabase(
    request: Request,
    path: str,
    *,
    method: str = "POST",
    payload: dict[str, Any] | None = None,
    bearer: str | None = None,
):
    base_url, anon_key = _auth_config(request)
    headers = {"apikey": anon_key, "Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    kwargs: dict[str, Any] = {"method": method, "headers": headers}
    if payload is not None:
        kwargs["body"] = json.dumps(payload)
    return await fetch(f"{base_url}{path}", **kwargs)


def validate_credentials(payload: dict[str, Any]) -> tuple[str, str]:
    email = str(payload.get("email", "")).strip().casefold()
    password = str(payload.get("password", ""))
    if len(email) > 320 or not EMAIL.fullmatch(email):
        raise HTTPException(422, "Enter a valid email address")
    if not 10 <= len(password) <= 128:
        raise HTTPException(422, "Password must contain 10 to 128 characters")
    return email, password


def _user_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    user = payload.get("user") or {}
    user_id = str(user.get("id", ""))
    email = str(user.get("email", "")).casefold()
    if not user_id or not email:
        raise HTTPException(502, "Authentication provider returned an incomplete user")
    return {"id": user_id, "email": email}


async def upsert_user(request: Request, user: dict[str, str]) -> None:
    stamp = now()
    await run(
        request,
        """
        INSERT INTO users (id, email, is_active, created_at, updated_at)
        VALUES (?, ?, 1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            email = CASE WHEN users.is_active = 1 THEN excluded.email ELSE users.email END,
            updated_at = excluded.updated_at
        """,
        user["id"],
        user["email"],
        stamp,
        stamp,
    )


async def delete_auth_user(request: Request, user_id: str) -> None:
    base_url = env_value(request, "SUPABASE_URL").rstrip("/")
    secret_key = env_value(request, "SUPABASE_SECRET_KEY")
    response = await fetch(
        f"{base_url}/auth/v1/admin/users/{user_id}",
        method="DELETE",
        headers={
            "apikey": secret_key,
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        },
    )
    if response.status not in (200, 204):
        body = await _json(response)
        message = body.get("msg") or body.get("message") or "Authentication provider rejected account deletion"
        raise HTTPException(502, message)


async def authenticate(request: Request, payload: dict[str, Any], path: str) -> dict[str, Any]:
    email, password = validate_credentials(payload)
    response = await _supabase(request, path, payload={"email": email, "password": password})
    body = await _json(response)
    if response.status >= 400:
        message = body.get("msg") or body.get("message") or body.get("error_description")
        if "email not confirmed" in str(message or "").casefold():
            raise HTTPException(403, "This account email is not confirmed")
        if response.status in (400, 401):
            raise HTTPException(401, "Invalid email or password")
        if response.status == 422:
            raise HTTPException(409, message or "An account with this email already exists")
        raise HTTPException(502, message or "Authentication provider is unavailable")
    if not body.get("access_token") or not body.get("refresh_token"):
        raise HTTPException(
            409,
            "Email confirmation is enabled. Confirm the address before signing in.",
        )
    user = _user_from_payload(body)
    await upsert_user(request, user)
    return {
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
        "token_type": body.get("token_type", "bearer"),
        "expires_in": int(body.get("expires_in", 3600)),
        "user": user,
    }


async def refresh_session(request: Request, refresh_token: str) -> dict[str, Any]:
    if not 8 <= len(refresh_token) <= 4096:
        raise HTTPException(422, "Invalid refresh token")
    response = await _supabase(
        request,
        "/auth/v1/token?grant_type=refresh_token",
        payload={"refresh_token": refresh_token},
    )
    body = await _json(response)
    if response.status >= 400:
        raise HTTPException(401, "Invalid or expired session")
    user = _user_from_payload(body)
    await upsert_user(request, user)
    return {
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
        "token_type": body.get("token_type", "bearer"),
        "expires_in": int(body.get("expires_in", 3600)),
        "user": user,
    }


async def current_user(request: Request) -> dict[str, str]:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not token:
        raise HTTPException(401, "Missing bearer token")
    response = await _supabase(request, "/auth/v1/user", method="GET", bearer=token)
    body = await _json(response)
    if response.status != 200:
        raise HTTPException(401, "Invalid or expired session")
    user = _user_from_payload({"user": body})
    await upsert_user(request, user)
    record = await first(request, "SELECT is_active FROM users WHERE id = ?", user["id"])
    if record is None or not bool(record.is_active):
        raise HTTPException(401, "Invalid or expired session")
    return user


async def require_consent(
    request: Request, user: dict[str, str] = Depends(current_user)
) -> dict[str, str]:
    missing = await first(
        request,
        """
        SELECT d.id
        FROM legal_documents d
        LEFT JOIN user_consents c
          ON c.legal_document_id = d.id AND c.user_id = ?
        WHERE d.active = 1 AND d.is_mandatory = 1 AND c.id IS NULL
        LIMIT 1
        """,
        user["id"],
    )
    if missing is not None:
        raise HTTPException(403, "Accept all current mandatory legal documents to continue.")
    return user
