"""Verifies the exact privacy boundary used to create the Workers AI prompt."""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from ai_privacy import AI_EXCLUDED_FIELDS, AI_PROFILE_FIELDS, private_profile_payload, safe_reason


signals = {
    "email": "must-not-leave@yudyai.xyz",
    "user_id": "private-user-id",
    "access_token": "private-access-token",
    "refresh_token": "private-refresh-token",
    "name": "Private Name",
    "risk_category": "Balanced",
    "risk_score_band": "40-49",
    "experience": "SOME",
    "investment_horizon": "THREE_FIVE",
    "goals": [{"title": "Diversification"}],
    "interests": [{"title": "AI & Technology"}],
    "excluded": [{"title": "Oil & Gas"}],
    "regions": [{"title": "United States"}],
    "liked_assets": ["AAPLx"],
    "saved_assets": ["SPYx"],
    "disliked_assets": ["TSLAx"],
}

payload = private_profile_payload(signals)
assert set(payload) == set(AI_PROFILE_FIELDS)
assert not set(AI_EXCLUDED_FIELDS) & set(payload)
serialized = repr(payload)
for value in (signals[field] for field in AI_EXCLUDED_FIELDS):
    assert value not in serialized
assert safe_reason("Selected because it matches your technology interest.")
assert safe_reason("You should buy this safe investment.") is None
assert safe_reason("Suitable for you with guaranteed returns.") is None
print("AI privacy boundary smoke test passed")
