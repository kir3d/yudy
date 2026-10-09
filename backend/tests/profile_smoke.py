"""Explicit local PostgreSQL/Redis integration smoke; never prints tokens."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE_URL = os.environ.get("PROFILE_SMOKE_URL", "http://localhost:8000") + "/api/v1"


def request(method, path, **kwargs):
    return httpx.request(method, BASE_URL + path, timeout=20, **kwargs)


def main():
    tokens = []
    try:
        for _ in range(2):
            response = request(
                "POST",
                "/auth/register",
                json={
                    "email": f"profile-smoke-{uuid.uuid4().hex}@example.com",
                    "password": "Local-profile-password-42",
                },
            )
            assert response.status_code == 201
            tokens.append(response.json()["data"])
        headers = [{"Authorization": "Bearer " + token["access_token"]} for token in tokens]
        options = {
            name: request("GET", "/" + name).json()["data"]
            for name in ("goals", "interests", "regions")
        }
        payload = {
            "experience": "NEW",
            "investment_horizon": "FIVE_PLUS",
            "goal_ids": [options["goals"][0]["id"]],
            "interest_ids": [options["interests"][0]["id"]],
            "excluded_interest_ids": [options["interests"][1]["id"]],
            "region_ids": [options["regions"][0]["id"]],
        }
        assert (
            request("POST", "/profile/onboarding", headers=headers[0], json=payload).status_code
            == 403
        )
        documents = request("GET", "/legal/documents").json()["data"]
        for header in headers:
            response = request(
                "POST",
                "/legal/consents",
                headers=header,
                json={
                    "consents": [
                        {"document_id": doc["id"], "version": doc["version"], "accepted": True}
                        for doc in documents
                    ]
                },
            )
            assert response.status_code == 200
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(
                executor.map(
                    lambda _: request(
                        "POST", "/profile/onboarding", headers=headers[0], json=payload
                    ),
                    range(2),
                )
            )
        assert all(response.status_code == 200 for response in responses)
        assert request("GET", "/profile", headers=headers[0]).json() == responses[0].json()
        assert request("GET", "/profile", headers=headers[1]).status_code == 404
        changed = {**payload, "experience": "EXPERIENCED", "interest_ids": [], "region_ids": []}
        response = request("PUT", "/profile", headers=headers[0], json=changed)
        assert response.status_code == 200
        assert request("GET", "/profile", headers=headers[0]).json() == response.json()
        invalid = {**changed, "goal_ids": [str(uuid.uuid4())]}
        assert request("PUT", "/profile", headers=headers[0], json=invalid).status_code == 422
        assert request("GET", "/profile", headers=headers[0]).json() == response.json()
        print(
            "PASS: consent guard, concurrent onboarding, persisted profile, editing, "
            "user isolation and atomic validation on PostgreSQL"
        )
    finally:
        for token in tokens:
            assert (
                request(
                    "POST", "/auth/logout", json={"refresh_token": token["refresh_token"]}
                ).status_code
                == 204
            )


if __name__ == "__main__":
    main()
