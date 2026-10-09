"""Local Buy redirect smoke; only demo transitions, no orders or credentials output."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import httpx

BASE = os.environ.get("BUY_SMOKE_URL", "http://localhost:8000") + "/api/v1"
PROVIDER = os.environ.get("DEMO_PROVIDER_SMOKE_URL", "http://localhost:8001")


def request(method, path, **kwargs):
    return httpx.request(method, BASE + path, timeout=20, **kwargs)


def main():
    session = None
    try:
        response = request(
            "POST",
            "/auth/register",
            json={
                "email": f"buy-smoke-{uuid.uuid4().hex}@example.com",
                "password": "Local-smoke-password-42",
            },
        )
        assert response.status_code == 201
        session = response.json()["data"]
        headers = {"Authorization": "Bearer " + session["access_token"]}
        docs = request("GET", "/legal/documents").json()["data"]
        assert (
            request(
                "POST",
                "/legal/consents",
                headers=headers,
                json={
                    "consents": [
                        {"document_id": d["id"], "version": d["version"], "accepted": True}
                        for d in docs
                    ]
                },
            ).status_code
            == 200
        )
        asset = request("GET", "/assets", params={"search": "DM01"}).json()["data"][0]
        path = "/assets/" + asset["id"]
        token = request("GET", path).json()["data"]["tokens"][0]
        preview = request(
            "GET", path + "/buy-link", headers=headers, params={"tokenized_asset_id": token["id"]}
        )
        assert preview.status_code == 200 and preview.headers["cache-control"] == "no-store"
        link = preview.json()["data"]
        assert link["demo"] and link["external"] and "token" not in urlsplit(link["url"]).query
        body = {"event_id": str(uuid.uuid4()), "tokenized_asset_id": token["id"]}
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(
                pool.map(
                    lambda _: request("POST", path + "/buy-click", headers=headers, json=body),
                    range(4),
                )
            )
        assert all(r.status_code == 200 and r.json() == preview.json() for r in responses)
        state = request("GET", path + "/interactions", headers=headers).json()["data"]
        assert state == dict(liked=False, disliked=False, saved=False)
        assert request("GET", "/saved", headers=headers).json()["data"] == []
        assert (
            request(
                "POST", path + "/buy-click", headers=headers, json={**body, "quantity": 1}
            ).status_code
            == 422
        )
        page_url = PROVIDER + urlsplit(link["url"]).path
        page = httpx.get(page_url, timeout=20)
        assert page.status_code == 200 and "No transaction has been performed" in page.text
        assert "<form" not in page.text
        assert httpx.post(page_url, timeout=20).status_code == 405
        assert httpx.post(PROVIDER + "/orders", timeout=20).status_code == 404
        print(
            "PASS: preview, concurrent confirmation retries, unchanged reactions "
            "and separate no-transaction provider"
        )
    finally:
        if session:
            assert (
                request(
                    "POST", "/auth/logout", json={"refresh_token": session["refresh_token"]}
                ).status_code
                == 204
            )


if __name__ == "__main__":
    main()
