"""Run inside the local backend container; verify HTTP events in PostgreSQL."""

import asyncio
import json
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sqlalchemy import select

from app.core.database import session_factory
from app.models.analytics import AnalyticsEvent

BASE = "http://localhost:8000/api/v1"


def request(method, path, headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(BASE + path, data=data, method=method,
                  headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(req, timeout=20) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except HTTPError as error:
        return error.code, None


def main():
    status, response = request("POST", "/auth/register", body={
        "email": f"analytics-smoke-{uuid.uuid4().hex}@example.com",
        "password": "Local-smoke-password-42",
    })
    assert status == 201
    tokens = response["data"]
    headers = {"Authorization": "Bearer " + tokens["access_token"]}
    try:
        docs = request("GET", "/legal/documents")[1]["data"]
        for _ in range(2):
            assert request("POST", "/legal/consents", headers, {"consents": [
                {"document_id": d["id"], "version": d["version"], "accepted": True}
                for d in docs
            ]})[0] == 200
        goal = request("GET", "/goals")[1]["data"][0]["id"]
        for _ in range(2):
            assert request("POST", "/profile/onboarding", headers, {
                "experience": "NEW", "investment_horizon": "FIVE_PLUS", "goal_ids": [goal]
            })[0] == 200
        questions = request("GET", "/risk/questions", headers)[1]["data"]
        assert request("POST", "/risk/assessment", headers, {
            "questionnaire_version": questions["questionnaire_version"],
            "answers": [{"question_id": q["id"], "option_id": q["options"][0]["id"]}
                        for q in questions["questions"]],
        })[0] == 200
        asset = request("GET", "/assets?search=DM01")[1]["data"][0]
        path = "/assets/" + asset["id"]
        for action in ("view", "like", "like", "save", "save", "dislike"):
            assert request("POST", path + "/" + action, headers)[0] == 200
        for _ in range(2):
            assert request("DELETE", path + "/save", headers)[0] == 200
        token = request("GET", path)[1]["data"]["tokens"][0]
        body = {"event_id": str(uuid.uuid4()), "tokenized_asset_id": token["id"]}
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(
                lambda _: request("POST", path + "/buy-click", headers, body), range(4)
            ))
        assert all(result[0] == 200 for result in results)
        assert request("POST", path + "/buy-click", headers, {**body, "quantity": 1})[0] == 422
        article = request("GET", "/learn/articles")[1]["data"][0]
        assert request("GET", "/learn/articles/" + article["slug"])[0] == 200

        async def verify():
            engine, factory = session_factory()
            try:
                async with factory() as session:
                    rows = list(await session.scalars(select(AnalyticsEvent).where(
                        AnalyticsEvent.user_id == uuid.UUID(tokens["user"]["id"])
                    )))
                    assert Counter(row.event_name for row in rows) == {
                        "registration_completed": 1, "legal_accepted": 1,
                        "onboarding_completed": 1, "risk_profile_completed": 1,
                        "asset_viewed": 1, "asset_liked": 1, "asset_disliked": 1,
                        "asset_saved": 1, "asset_unsaved": 1, "buy_clicked": 1,
                    }
                    anonymous = await session.scalar(select(AnalyticsEvent).where(
                        AnalyticsEvent.event_name == "learn_article_opened",
                        AnalyticsEvent.user_id.is_(None),
                    ).order_by(AnalyticsEvent.created_at.desc()))
                    assert anonymous.properties["article_id"] == article["id"]
                    buy = next(row for row in rows if row.event_name == "buy_clicked")
                    assert buy.properties["interaction_id"] == body["event_id"]
            finally:
                await engine.dispose()

        asyncio.run(verify())
        print("PASS: all 11 analytics events persisted; concurrent Buy retries counted once")
    finally:
        assert request("POST", "/auth/logout", body={
            "refresh_token": tokens["refresh_token"]
        })[0] == 204


if __name__ == "__main__":
    main()
