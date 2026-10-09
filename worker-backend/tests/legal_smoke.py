"""Validate one-action legal acceptance and the user-level agreement timestamp."""

from smoke import request


def main() -> None:
    auth = request(
        "/api/v1/auth/register",
        "POST",
        {"email": "test@yudyai.xyz", "password": "correct-horse-battery"},
    )["data"]
    token = auth["access_token"]
    assert request("/api/v1/users/me", token=token)["data"]["agreements_accepted_at"] is None
    documents = request("/api/v1/legal/documents")["data"]
    body = {"consents": [
        {"document_id": item["id"], "version": item["version"], "accepted": True}
        for item in documents
    ]}
    accepted = request("/api/v1/legal/consents", "POST", body, token)["data"]
    accepted_at = accepted["agreements_accepted_at"]
    assert accepted["all_required_accepted"] is True
    assert accepted_at
    assert request("/api/v1/users/me", token=token)["data"]["agreements_accepted_at"] == accepted_at
    repeated = request("/api/v1/legal/consents", "POST", body, token)["data"]
    assert repeated["agreements_accepted_at"] == accepted_at
    print("one-action legal acceptance smoke test passed")


if __name__ == "__main__":
    main()
