"""End-to-end contract smoke test for the local Worker and D1 database."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid


BASE = "http://127.0.0.1:8787"


def request(path: str, method: str = "GET", payload=None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status == 204:
            return None
        return json.loads(response.read())


def main() -> None:
    assert request("/health")["data"]["database"] is True
    auth = request(
        "/api/v1/auth/register",
        "POST",
        {"email": "test@yudyai.xyz", "password": "correct-horse-battery"},
    )["data"]
    token = auth["access_token"]
    current_user = request("/api/v1/users/me", token=token)["data"]
    assert current_user["email"] == "test@yudyai.xyz"
    assert current_user["agreements_accepted_at"] is None

    documents = request("/api/v1/legal/documents")["data"]
    consent = request(
        "/api/v1/legal/consents",
        "POST",
        {
            "consents": [
                {"document_id": item["id"], "version": item["version"], "accepted": True}
                for item in documents
            ]
        },
        token,
    )["data"]
    assert consent["all_required_accepted"] is True
    assert consent["agreements_accepted_at"]
    assert request("/api/v1/users/me", token=token)["data"]["agreements_accepted_at"] == consent["agreements_accepted_at"]

    goal = request("/api/v1/goals")["data"][0]
    interest = request("/api/v1/interests")["data"][0]
    region = request("/api/v1/regions")["data"][0]
    profile = request(
        "/api/v1/profile/onboarding",
        "POST",
        {
            "experience": "NEW",
            "investment_horizon": "FIVE_PLUS",
            "goal_ids": [goal["id"]],
            "interest_ids": [interest["id"]],
            "excluded_interest_ids": [],
            "region_ids": [region["id"]],
        },
        token,
    )["data"]
    assert profile["onboarding_completed"] is True

    questionnaire = request("/api/v1/risk/questions", token=token)["data"]
    risk = request(
        "/api/v1/risk/assessment",
        "POST",
        {
            "questionnaire_version": questionnaire["questionnaire_version"],
            "answers": [
                {"question_id": question["id"], "option_id": question["options"][0]["id"]}
                for question in questionnaire["questions"]
            ],
        },
        token,
    )["data"]
    assert risk["is_current"] is True

    xstocks = request("/api/v1/selection/xstocks?limit=4", token=token)
    assert len(xstocks["data"]) == 4
    assert xstocks["meta"]["data_mode"] == "live_xstocks"
    assert "email" in xstocks["meta"]["privacy"]["never_sent"]
    assert all(item["symbol"].endswith("x") and item["reason"] for item in xstocks["data"])

    catalog = request("/api/v1/assets?limit=1")
    asset = catalog["data"][0]
    state = request(f"/api/v1/assets/{asset['id']}/save", "POST", token=token)["data"]
    assert state["saved"] is True
    assert request("/api/v1/saved", token=token)["data"][0]["id"] == asset["id"]
    assert request("/api/v1/selection/for-you?limit=5", token=token)["data"]

    detail = request(f"/api/v1/assets/{asset['id']}")["data"]
    link = request(
        f"/api/v1/assets/{asset['id']}/buy-link?"
        + urllib.parse.urlencode({"tokenized_asset_id": detail["tokens"][0]["id"]}),
        token=token,
    )["data"]
    assert link["external"] is True and link["demo"] is True
    confirmed = request(
        f"/api/v1/assets/{asset['id']}/buy-click",
        "POST",
        {"event_id": str(uuid.uuid4()), "tokenized_asset_id": detail["tokens"][0]["id"]},
        token,
    )["data"]
    assert confirmed["url"] == link["url"]
    refreshed = request(
        "/api/v1/auth/refresh",
        "POST",
        {"refresh_token": auth["refresh_token"]},
    )["data"]
    assert refreshed["access_token"] == "local-access-token"
    request(
        "/api/v1/auth/logout",
        "POST",
        {"refresh_token": refreshed["refresh_token"]},
    )
    print("worker smoke test passed")


if __name__ == "__main__":
    main()
