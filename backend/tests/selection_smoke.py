"""Local PostgreSQL/Redis personalized feed smoke; no credentials printed."""

import os
import uuid

import httpx

BASE_URL = os.environ.get("SELECTION_SMOKE_URL", "http://localhost:8000") + "/api/v1"


def request(method, path, **kwargs):
    return httpx.request(method, BASE_URL + path, timeout=20, **kwargs)


def main():
    sessions = []
    try:
        documents = request("GET", "/legal/documents").json()["data"]
        goals = request("GET", "/goals").json()["data"]
        interests = request("GET", "/interests").json()["data"]
        automotive = next(i["id"] for i in interests if i["code"] == "automotive")
        for _ in range(2):
            r = request(
                "POST",
                "/auth/register",
                json={
                    "email": f"selection-smoke-{uuid.uuid4().hex}@example.com",
                    "password": "Local-smoke-password-42",
                },
            )
            assert r.status_code == 201
            sessions.append(r.json()["data"])
        headers = [{"Authorization": "Bearer " + s["access_token"]} for s in sessions]
        for header in headers:
            assert request("GET", "/selection/for-you", headers=header).status_code == 403
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
            assert (
                request(
                    "POST",
                    "/profile/onboarding",
                    headers=header,
                    json={
                        "experience": "EXPERIENCED",
                        "investment_horizon": "UNDER_ONE",
                        "goal_ids": [next(g["id"] for g in goals if g["code"] == "exploring")],
                        "interest_ids": [automotive],
                    },
                ).status_code
                == 200
            )
            q = request("GET", "/risk/questions", headers=header).json()["data"]
            assert (
                request(
                    "POST",
                    "/risk/assessment",
                    headers=header,
                    json={
                        "questionnaire_version": q["questionnaire_version"],
                        "answers": [
                            {
                                "question_id": question["id"],
                                "option_id": question["options"][3]["id"],
                            }
                            for question in q["questions"]
                        ],
                    },
                ).status_code
                == 200
            )

        def feed(header, **params):
            r = request("GET", "/selection/for-you", headers=header, params=params)
            assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
            assert "score" not in r.text
            return r.json()

        first = feed(headers[0], limit=7)
        assert feed(headers[0], limit=7) == first
        items = list(first["data"])
        cursor = first["meta"]["next_cursor"]
        while cursor:
            page = feed(headers[0], limit=7, cursor=cursor)
            items.extend(page["data"])
            cursor = page["meta"]["next_cursor"]
        assert len(items) == len({i["asset"]["id"] for i in items}) == 36
        assert items[0]["asset"]["sector"] == "Automotive"
        assert all(1 <= len(i["reasons"]) <= 3 for i in items)
        before = feed(headers[0], limit=50)
        catalog = request("GET", "/assets", params={"limit": 50}).json()
        asset_id = before["data"][0]["asset"]["id"]
        assert request("POST", f"/assets/{asset_id}/dislike", headers=headers[0]).status_code == 200
        after = feed(headers[0], limit=50)
        assert after["data"][0]["asset"]["id"] != asset_id
        assert (
            request(
                "GET",
                "/selection/for-you",
                headers=headers[0],
                params={"cursor": first["meta"]["next_cursor"]},
            ).status_code
            == 400
        )
        assert request("GET", "/assets", params={"limit": 50}).json() == catalog
        other = feed(headers[1], limit=50)
        assert all(not i["interaction"]["disliked"] for i in other["data"])
        assert (
            request(
                "GET",
                "/selection/for-you",
                headers=headers[1],
                params={"cursor": first["meta"]["next_cursor"]},
            ).status_code
            == 400
        )
        assert request("POST", f"/assets/{asset_id}/save", headers=headers[0]).status_code == 200
        item = next(i for i in feed(headers[0], limit=50)["data"] if i["asset"]["id"] == asset_id)
        assert item["interaction"]["saved"] and not item["interaction"]["liked"]
        print(
            "PASS: personalized ranking, reasons, pagination, action refresh, "
            "isolation and unchanged Discover"
        )
    finally:
        for s in sessions:
            assert (
                request(
                    "POST", "/auth/logout", json={"refresh_token": s["refresh_token"]}
                ).status_code
                == 204
            )


if __name__ == "__main__":
    main()
