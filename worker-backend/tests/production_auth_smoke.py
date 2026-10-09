"""Create and validate one disposable production auth session."""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.request
import uuid


BASE = "https://api.yudyai.xyz"


def call(path: str, method: str = "GET", payload=None, token: str | None = None):
    headers = {"Content-Type": "application/json", "User-Agent": "okhttp/4.12.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status == 204:
                return None
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} returned {error.code}: {detail}") from None


def main() -> None:
    email = f"deployment-check-{uuid.uuid4().hex[:12]}@yudyai.xyz"
    password = secrets.token_urlsafe(24)
    auth = call(
        "/api/v1/auth/register",
        "POST",
        {"email": email, "password": password},
    )["data"]
    access_token = auth["access_token"]
    refresh_token = auth["refresh_token"]
    me = call("/api/v1/users/me", token=access_token)["data"]
    assert me["id"] == auth["user"]["id"]
    assert me["email"] == email
    call(
        "/api/v1/auth/logout",
        "POST",
        {"refresh_token": refresh_token},
    )
    signed_in = call(
        "/api/v1/auth/login",
        "POST",
        {"email": email, "password": password},
    )["data"]
    assert signed_in["user"]["id"] == auth["user"]["id"]
    signed_in_me = call("/api/v1/users/me", token=signed_in["access_token"])["data"]
    assert signed_in_me["email"] == email
    refreshed = call(
        "/api/v1/auth/refresh",
        "POST",
        {"refresh_token": signed_in["refresh_token"]},
    )["data"]
    assert refreshed["access_token"]
    call(
        "/api/v1/auth/logout",
        "POST",
        {"refresh_token": refreshed["refresh_token"]},
    )
    print(json.dumps({"email": email, "user_id": me["id"], "status": "passed"}))


if __name__ == "__main__":
    main()
