import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from redis.exceptions import ConnectionError

from app.core.config import Settings
from app.core.errors import install_error_handlers
from app.core.http import install_http_middleware
from app.services.rate_limit import AuthRateLimiter


def hardened_app():
    app = FastAPI()
    install_error_handlers(app)
    install_http_middleware(app, Settings(
        app_env="production", cors_origins=["https://allowed.example"]
    ))

    @app.get("/api/failure")
    async def failure():
        raise ValueError("secret-canary-password-and-sql-parameters")

    return app


def test_unexpected_errors_are_sanitized_in_response_and_logs(caplog):
    client = TestClient(hardened_app(), base_url="https://testserver")
    response = client.get("/api/failure", headers={"Origin": "https://allowed.example"})
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "INTERNAL_ERROR",
                                         "message": "An internal error occurred"}}
    assert "secret-canary" not in response.text + caplog.text
    assert "ValueError" in caplog.text
    assert response.headers["access-control-allow-origin"] == "https://allowed.example"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["strict-transport-security"] == "max-age=31536000"


def test_cors_preflight_restricts_origins_methods_and_headers():
    client = TestClient(hardened_app())
    headers = {"Origin": "https://allowed.example", "Access-Control-Request-Method": "POST",
               "Access-Control-Request-Headers": "Authorization, Content-Type"}
    assert client.options("/api/test", headers=headers).status_code == 200
    for changed in ({"Origin": "https://other.example"},
                    {"Access-Control-Request-Method": "PATCH"},
                    {"Access-Control-Request-Headers": "X-Unknown"}):
        response = client.options("/api/test", headers={**headers, **changed})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "HTTP_400"
        assert response.headers["x-content-type-options"] == "nosniff"
    assert "strict-transport-security" not in client.get("/missing").headers


@pytest.mark.parametrize("origin", ["*", "https://*.example", "https://user:pass@example.com",
                                    "https://example.com/path", "null", "ftp://example.com"])
def test_cors_config_rejects_wildcards_and_non_origins(origin):
    with pytest.raises(ValidationError):
        Settings(cors_origins=[origin])


def test_auth_extra_fields_and_invalid_bodies_do_not_echo_secrets(client):
    for path, body in (("register", {"email": "test@example.com", "password": "test-password-42",
                                   "is_admin": True}),
                       ("refresh", {"refresh_token": "secret-canary" * 5, "user_id": "other"})):
        response = client.post("/api/v1/auth/" + path, json=body)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert "secret-canary" not in response.text
    response = client.post("/api/v1/auth/register", content='{"password":"secret-canary",',
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 422 and "secret-canary" not in response.text


def test_redis_connection_failure_fails_closed():
    class BrokenRedis:
        async def eval(self, *args):
            raise ConnectionError("private connection details")

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        asyncio.run(AuthRateLimiter(BrokenRedis(), Settings()).check("127.0.0.1"))
    assert error.value.status_code == 503
    assert "private" not in error.value.detail
