"""Explicit local Compose smoke test; creates isolated test users, prints no tokens."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE_URL = os.environ.get("LEGAL_SMOKE_URL", "http://localhost:8000")


def request(method, path, **kwargs):
    return httpx.request(method, BASE_URL + "/api/v1" + path, timeout=20, **kwargs)


def sign_in():
    response = request(
        "POST",
        "/auth/register",
        json={
            "email": f"legal-smoke-{uuid.uuid4().hex}@example.com",
            "password": "Legal-smoke-password-42",
        },
    )
    assert response.status_code == 201, response.status_code
    tokens = response.json()["data"]
    return tokens, {"Authorization": "Bearer " + tokens["access_token"]}


def main():
    first_tokens, first = sign_in()
    second_tokens, second = sign_in()
    response = request("GET", "/legal/documents")
    assert response.status_code == 200
    docs = response.json()["data"]
    assert len(docs) == 3
    assert not request("GET", "/legal/consents/me", headers=first).json()["data"][
        "all_required_accepted"
    ]
    body = {
        "consents": [
            {"document_id": doc["id"], "version": doc["version"], "accepted": True} for doc in docs
        ]
    }
    partial = request(
        "POST", "/legal/consents", headers=first, json={"consents": body["consents"][:1]}
    )
    assert partial.status_code == 200
    assert not partial.json()["data"]["all_required_accepted"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: request("POST", "/legal/consents", headers=first, json=body), range(2)
            )
        )
    assert all(result.status_code == 200 for result in results)
    assert results[0].json() == results[1].json()
    completed = results[0].json()["data"]
    assert completed["all_required_accepted"]
    assert all(doc["accepted_at"] and doc["accepted"] for doc in completed["documents"])
    assert not request("GET", "/legal/consents/me", headers=second).json()["data"][
        "all_required_accepted"
    ]
    stale = {"consents": [{**body["consents"][0], "version": "outdated-version"}]}
    assert request("POST", "/legal/consents", headers=first, json=stale).status_code == 409
    assert request("GET", "/legal/consents/me").status_code == 401
    for tokens in (first_tokens, second_tokens):
        assert (
            request(
                "POST", "/auth/logout", json={"refresh_token": tokens["refresh_token"]}
            ).status_code
            == 204
        )
    print(
        "PASS: legal documents, partial/full consent, concurrent idempotency, "
        "isolation and stale versions"
    )


if __name__ == "__main__":
    main()
