import asyncio
from datetime import timedelta

import jwt
import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.core.security import decode_access_token
from app.models.auth import utcnow
from app.services.rate_limit import AuthRateLimiter

CREDENTIALS = {"email": "Explorer@example.com", "password": "long-password-42"}


def register(client):
    response = client.post("/api/v1/auth/register", json=CREDENTIALS)
    assert response.status_code == 201, response.text
    assert response.headers["Cache-Control"] == "no-store"
    return response.json()["data"]


def test_register_login_and_me_hide_sensitive_fields(client):
    data = register(client)
    assert data["user"]["email"] == "explorer@example.com"
    assert set(data["user"]) == {"id", "email"}
    assert data["expires_in"] == 900
    me = client.get("/api/v1/users/me", headers={"Authorization": "Bearer " + data["access_token"]})
    assert me.status_code == 200
    assert me.json()["data"] == data["user"]
    login = client.post("/api/v1/auth/login", json=CREDENTIALS)
    assert login.status_code == 200
    assert login.json()["data"]["access_token"] != data["access_token"]
    assert client.get("/api/v1/users/me").status_code == 401


def test_duplicate_email_is_case_insensitive(client):
    register(client)
    assert (
        client.post(
            "/api/v1/auth/register", json={**CREDENTIALS, "email": "explorer@example.com"}
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "credentials",
    [
        {"email": "invalid", "password": "long-password-42"},
        {"email": "test@example.com", "password": "short"},
        {"email": "test@example.com", "password": "x" * 129},
    ],
)
def test_invalid_registration(client, credentials):
    response = client.post("/api/v1/auth/register", json=credentials)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert credentials["password"] not in response.text


def test_wrong_credentials_are_generic(client):
    register(client)
    wrong_password = client.post(
        "/api/v1/auth/login", json={**CREDENTIALS, "password": "not-the-password"}
    )
    unknown_user = client.post(
        "/api/v1/auth/login", json={**CREDENTIALS, "email": "unknown@example.com"}
    )
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


def test_rotation_and_logout_revoke_access_and_refresh(client):
    old = register(client)
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
    assert refreshed.status_code == 200
    new = refreshed.json()["data"]
    assert new["refresh_token"] != old["refresh_token"]
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer " + old["access_token"]}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer " + new["access_token"]}
        ).status_code
        == 200
    )
    for _ in range(2):
        assert (
            client.post(
                "/api/v1/auth/logout", json={"refresh_token": new["refresh_token"]}
            ).status_code
            == 204
        )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer " + new["access_token"]}
        ).status_code
        == 401
    )


def test_tampered_token_rejected(client):
    data = register(client)
    token = data["access_token"]
    parts = token.split(".")
    parts[1] = parts[1][::-1]
    assert (
        client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer " + ".".join(parts)}
        ).status_code
        == 401
    )


def test_expired_access_token_rejected():
    settings = Settings(jwt_secret="test-key-only-" + "x" * 32)
    token = jwt.encode(
        {
            "sub": "not-important",
            "sid": "not-important",
            "iss": "yudy",
            "iat": utcnow() - timedelta(hours=2),
            "exp": utcnow() - timedelta(hours=1),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as error:
        decode_access_token(token, settings)
    assert error.value.status_code == 401


def test_rate_limit_endpoint(client):
    for _ in range(20):
        client.post("/api/v1/auth/login", json={"email": "invalid", "password": "short"})
    assert client.post("/api/v1/auth/login", json=CREDENTIALS).status_code == 429


def test_rate_limiter_fails_closed():
    with pytest.raises(HTTPException) as error:
        asyncio.run(AuthRateLimiter(None, Settings()).check("127.0.0.1"))
    assert error.value.status_code == 503
