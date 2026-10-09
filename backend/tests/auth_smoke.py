"""Run explicitly against a local Compose stack; no tokens are printed."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

base_url = os.environ.get("AUTH_SMOKE_URL", "http://localhost:8000")
credentials = {
    "email": f"smoke-{uuid.uuid4().hex}@example.com",
    "password": "Local-smoke-password-42",
}


def request(method, path, **kwargs):
    return httpx.request(method, base_url + "/api/v1" + path, timeout=20, **kwargs)


def check_me(tokens, expected=200):
    response = request(
        "GET", "/users/me", headers={"Authorization": "Bearer " + tokens["access_token"]}
    )
    assert response.status_code == expected, response.status_code
    if expected == 200:
        assert response.json()["data"]["email"] == credentials["email"]


def main():
    response = request("POST", "/auth/register", json=credentials)
    assert response.status_code == 201, response.status_code
    registered = response.json()["data"]
    check_me(registered)
    response = request("POST", "/auth/login", json=credentials)
    assert response.status_code == 200, response.status_code
    logged_in = response.json()["data"]
    check_me(logged_in)
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: request(
                    "POST", "/auth/refresh", json={"refresh_token": logged_in["refresh_token"]}
                ),
                range(2),
            )
        )
    assert sorted(r.status_code for r in responses) == [200, 401]
    rotated = next(r.json()["data"] for r in responses if r.status_code == 200)
    check_me(logged_in, 401)
    check_me(rotated)
    for tokens in (registered, rotated):
        assert (
            request(
                "POST", "/auth/logout", json={"refresh_token": tokens["refresh_token"]}
            ).status_code
            == 204
        )
        check_me(tokens, 401)
    print("PASS: register, login, me, concurrent refresh rotation and logout on PostgreSQL/Redis")


if __name__ == "__main__":
    main()
