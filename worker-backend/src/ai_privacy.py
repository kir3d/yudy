from __future__ import annotations

from typing import Any


AI_PROFILE_FIELDS = (
    "risk_category",
    "risk_score_band",
    "experience",
    "investment_horizon",
    "goals",
    "interests",
    "excluded_interests",
    "regions",
    "liked_assets",
    "saved_assets",
    "disliked_assets",
)

AI_EXCLUDED_FIELDS = ("email", "name", "user_id", "access_token", "refresh_token")

FORBIDDEN_REASON_PHRASES = (
    "you should",
    "should buy",
    "recommended investment",
    "best investment",
    "suitable for you",
    "safe investment",
    "guaranteed return",
    "guaranteed returns",
)


def private_profile_payload(signals: dict[str, Any]) -> dict[str, Any]:
    return {
        "risk_category": signals["risk_category"],
        "risk_score_band": signals["risk_score_band"],
        "experience": signals["experience"],
        "investment_horizon": signals["investment_horizon"],
        "goals": [item["title"] for item in signals["goals"]],
        "interests": [item["title"] for item in signals["interests"]],
        "excluded_interests": [item["title"] for item in signals["excluded"]],
        "regions": [item["title"] for item in signals["regions"]],
        "liked_assets": list(signals.get("liked_assets", [])),
        "saved_assets": list(signals.get("saved_assets", [])),
        "disliked_assets": list(signals.get("disliked_assets", [])),
    }


def safe_reason(value: Any) -> str | None:
    reason = " ".join(str(value or "").split())[:220]
    lowered = reason.casefold()
    if not reason or any(phrase in lowered for phrase in FORBIDDEN_REASON_PHRASES):
        return None
    return reason
