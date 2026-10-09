"""Local PostgreSQL interaction smoke; revokes test sessions, prints no credentials."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE_URL = os.environ.get("INTERACTIONS_SMOKE_URL", "http://localhost:8000") + "/api/v1"


def request(method, path, **kwargs):
    return httpx.request(method, BASE_URL + path, timeout=20, **kwargs)


def main():
    sessions = []
    try:
        documents = request("GET", "/legal/documents").json()["data"]
        for _ in range(2):
            response = request(
                "POST",
                "/auth/register",
                json={
                    "email": f"interaction-smoke-{uuid.uuid4().hex}@example.com",
                    "password": "Local-smoke-password-42",
                },
            )
            assert response.status_code == 201
            sessions.append(response.json()["data"])
        headers = [{"Authorization": "Bearer " + s["access_token"]} for s in sessions]
        assert request("GET", "/saved", headers=headers[0]).status_code == 403
        for header in headers:
            assert (
                request(
                    "POST",
                    "/legal/consents",
                    headers=header,
                    json={
                        "consents": [
                            {"document_id": d["id"], "version": d["version"], "accepted": True}
                            for d in documents
                        ]
                    },
                ).status_code
                == 200
            )
        assets = request("GET", "/assets", params={"limit": 50}).json()["data"]
        asset = assets[0]["id"]

        def act(action, method="POST"):
            response = request(method, f"/assets/{asset}/{action}", headers=headers[0])
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            return response.json()["data"]

        assert act("view") == dict(liked=False, disliked=False, saved=False)
        assert act("like")["liked"]
        assert request("GET", "/saved", headers=headers[0]).json()["data"] == []
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: act("save"), range(4)))
        assert all(r["saved"] for r in results)
        assert len(request("GET", "/saved", headers=headers[0]).json()["data"]) == 1
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(act, ("like", "dislike")))
        state = request("GET", f"/assets/{asset}/interactions", headers=headers[0]).json()["data"]
        assert state["liked"] != state["disliked"] and state["saved"]
        assert request("GET", "/saved", headers=headers[1]).json()["data"] == []
        assert not request("GET", f"/assets/{asset}/interactions", headers=headers[1]).json()[
            "data"
        ]["saved"]
        act("like", "DELETE")
        act("dislike", "DELETE")
        act("save", "DELETE")
        assert request("GET", "/saved", headers=headers[0]).json()["data"] == []
        print(
            "PASS: independent Like/Save, undo, view, private Saved "
            "and concurrent PostgreSQL writes"
        )
    finally:
        for session in sessions:
            assert (
                request(
                    "POST", "/auth/logout", json={"refresh_token": session["refresh_token"]}
                ).status_code
                == 204
            )


if __name__ == "__main__":
    main()
