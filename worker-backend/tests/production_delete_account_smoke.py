"""Validate deployed account deletion after SUPABASE_SECRET_KEY is installed."""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.request
import uuid


BASE = "https://api.yudyai.xyz"


def call(path: str, method: str = "GET", payload=None, token: str | None = None):
    headers = {"Content-Type": "application/json", "User-Agent": "YUDY deletion smoke"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return None if response.status == 204 else json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode(errors="replace")


def main() -> None:
    email = f"delete-check-{uuid.uuid4().hex[:12]}@yudyai.xyz"
    password = secrets.token_urlsafe(24)
    registered = call(
        "/api/v1/auth/register",
        "POST",
        {"email": email, "password": password},
    )
    assert isinstance(registered, dict), registered
    token = registered["data"]["access_token"]
    assert call("/api/v1/users/me", "DELETE", token=token) is None

    current = call("/api/v1/users/me", token=token)
    assert isinstance(current, tuple) and current[0] == 401, current
    login = call(
        "/api/v1/auth/login",
        "POST",
        {"email": email, "password": password},
    )
    assert isinstance(login, tuple) and login[0] == 401, login
    print(json.dumps({"status": "passed", "account": "deleted"}))


if __name__ == "__main__":
    main()
