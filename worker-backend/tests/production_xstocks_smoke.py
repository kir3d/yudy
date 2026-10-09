"""Validate the deployed anonymous-profile Workers AI and official xStocks flow."""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.request
import uuid
from pathlib import Path


BASE = "https://api.yudyai.xyz"
SESSION_FILE = Path("/tmp/yudy-production-xstocks-session.json")


def call(path: str, method: str = "GET", payload=None, token: str | None = None):
    headers = {"Content-Type": "application/json", "User-Agent": "okhttp/4.12.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status == 204:
                return None
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} returned {error.code}: {detail}") from None


def main() -> None:
    if SESSION_FILE.exists():
        saved = json.loads(SESSION_FILE.read_text())
        email, password = saved["email"], saved["password"]
        auth = call("/api/v1/auth/login", "POST", {"email": email, "password": password})["data"]
    else:
        email = f"ai-check-{uuid.uuid4().hex[:12]}@yudyai.xyz"
        password = secrets.token_urlsafe(24)
        auth = call("/api/v1/auth/register", "POST", {"email": email, "password": password})["data"]
        SESSION_FILE.write_text(json.dumps({"email": email, "password": password}))
    token = auth["access_token"]
    documents = call("/api/v1/legal/documents")["data"]
    consent = call("/api/v1/legal/consents", "POST", {"consents": [
        {"document_id": item["id"], "version": item["version"], "accepted": True}
        for item in documents
    ]}, token)["data"]
    assert consent["agreements_accepted_at"]
    assert call("/api/v1/users/me", token=token)["data"]["agreements_accepted_at"] == consent["agreements_accepted_at"]
    goals = call("/api/v1/goals")["data"]
    interests = call("/api/v1/interests")["data"]
    regions = call("/api/v1/regions")["data"]
    call("/api/v1/profile/onboarding", "POST", {
        "experience": "SOME",
        "investment_horizon": "THREE_FIVE",
        "goal_ids": [goals[0]["id"]],
        "interest_ids": [interests[0]["id"]],
        "excluded_interest_ids": [],
        "region_ids": [regions[0]["id"]],
    }, token)
    questionnaire = call("/api/v1/risk/questions", token=token)["data"]
    call("/api/v1/risk/assessment", "POST", {
        "questionnaire_version": questionnaire["questionnaire_version"],
        "answers": [
            {"question_id": question["id"], "option_id": question["options"][1]["id"]}
            for question in questionnaire["questions"]
        ],
    }, token)
    existing = call("/api/v1/xstocks?limit=50", token=token)["data"]
    for item in existing:
        state = item["interaction"]
        for action, field in (("like", "liked"), ("dislike", "disliked"), ("save", "saved")):
            if state[field]:
                call(f"/api/v1/xstocks/{item['id']}/{action}", "DELETE", token=token)
    result = call("/api/v1/selection/xstocks?limit=4", token=token)
    assert result["meta"]["data_mode"] == "live_xstocks"
    assert set(result["meta"]["privacy"]["never_sent"]) == {
        "email", "name", "user_id", "access_token", "refresh_token"
    }
    assert len(result["data"]) == 4
    assert all(item["symbol"].endswith("x") and item["reason"] for item in result["data"])
    assert all(item["logo_url"] for item in result["data"])
    assert all(len(item["sparkline_7d"]) > 20 for item in result["data"])
    assert all(item["price_change_percentage_7d"] is not None for item in result["data"])
    assert {"liked_assets", "saved_assets", "disliked_assets"} <= set(
        result["meta"]["privacy"]["sent_to_ai"]
    )

    catalog = call("/api/v1/xstocks?limit=50", token=token)
    assert catalog["meta"]["data_mode"] == "live_xstocks"
    assert catalog["meta"]["total"] >= 40
    assert all(item["symbol"].endswith("x") for item in catalog["data"])
    asset = result["data"][0]
    asset_id, symbol = asset["id"], asset["symbol"]

    liked = call(f"/api/v1/xstocks/{asset_id}/like", "POST", token=token)["data"]
    assert liked == {"liked": True, "disliked": False, "saved": False}
    saved = call(f"/api/v1/xstocks/{asset_id}/save", "POST", token=token)["data"]
    assert saved["liked"] is True and saved["saved"] is True
    assert asset_id in {item["id"] for item in call("/api/v1/xstocks/saved", token=token)["data"]}

    disliked = call(f"/api/v1/xstocks/{asset_id}/dislike", "POST", token=token)["data"]
    assert disliked == {"liked": False, "disliked": True, "saved": True}
    refreshed = call("/api/v1/selection/xstocks?limit=4", token=token)
    assert symbol not in {item["symbol"] for item in refreshed["data"]}
    discover_match = call(f"/api/v1/xstocks?search={symbol}", token=token)["data"]
    assert discover_match and discover_match[0]["interaction"]["disliked"] is True

    venues = call(f"/api/v1/xstocks/{asset_id}/venues", token=token)["data"]
    assert {venue["name"] for venue in venues} >= {"Kraken", "Jupiter"}
    assert all(venue["url"].startswith("https://") for venue in venues)
    call(f"/api/v1/xstocks/{asset_id}/buy-click", "POST", {"venue": "Jupiter"}, token)

    call(f"/api/v1/xstocks/{asset_id}/dislike", "DELETE", token=token)
    call(f"/api/v1/xstocks/{asset_id}/save", "DELETE", token=token)
    call("/api/v1/auth/logout", "POST", {"refresh_token": auth["refresh_token"]})
    SESSION_FILE.unlink(missing_ok=True)
    print(json.dumps({"email": email, "user_id": auth["user"]["id"],
        "symbols": [item["symbol"] for item in result["data"]], "status": "passed"}))


if __name__ == "__main__":
    main()
