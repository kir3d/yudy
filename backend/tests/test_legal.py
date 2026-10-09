import uuid

import pytest
from fastapi import Depends
from sqlalchemy import func, select, update

from app.api.legal import require_legal_consent
from app.core.config import Settings
from app.main import app
from app.models.legal import LegalDocument, LegalDocumentType, UserConsent
from app.services.legal_seed import seed_legal_documents


def sign_in(client, email="legal@example.com"):
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "legal-password-42"}
    )
    assert response.status_code == 201
    return {"Authorization": "Bearer " + response.json()["data"]["access_token"]}


def documents(client):
    return client.get("/api/v1/legal/documents").json()["data"]


def payload(docs):
    return {
        "consents": [
            {"document_id": doc["id"], "version": doc["version"], "accepted": True} for doc in docs
        ]
    }


def state(client, headers):
    response = client.get("/api/v1/legal/consents/me", headers=headers)
    assert response.status_code == 200
    return response.json()["data"]


def test_seeded_documents_are_readable_and_not_implicitly_accepted(client):
    docs = documents(client)
    assert len(docs) == 3
    assert {doc["type"] for doc in docs} == set(LegalDocumentType)
    assert all(doc["content"] and doc["is_mandatory"] and doc["version"] for doc in docs)
    headers = sign_in(client)
    current = state(client, headers)
    assert not current["all_required_accepted"]
    assert all(not doc["accepted"] and doc["accepted_at"] is None for doc in current["documents"])
    assert client.get("/api/v1/legal/consents/me").status_code == 401
    assert client.post("/api/v1/legal/consents", json=payload(docs)).status_code == 401


def test_acceptance_is_versioned_timestamped_and_idempotent(client):
    headers = sign_in(client)
    body = payload(documents(client))
    first = client.post("/api/v1/legal/consents", headers=headers, json=body)
    assert first.status_code == 200
    accepted = first.json()["data"]
    assert accepted["all_required_accepted"]
    assert all(doc["accepted"] and doc["accepted_at"] for doc in accepted["documents"])
    repeated = client.post("/api/v1/legal/consents", headers=headers, json=body)
    assert repeated.json()["data"] == accepted
    assert state(client, headers) == accepted

    async def check_count():
        async with client.db_factory() as session:
            return await session.scalar(select(func.count()).select_from(UserConsent))

    assert client.portal.call(check_count) == 3


def test_partial_acceptance_does_not_complete_or_leak_to_another_user(client):
    first = sign_in(client)
    second = sign_in(client, "another@example.com")
    client.post("/api/v1/legal/consents", headers=first, json=payload(documents(client)[:1]))
    assert not state(client, first)["all_required_accepted"]
    assert sum(doc["accepted"] for doc in state(client, first)["documents"]) == 1
    assert all(not doc["accepted"] for doc in state(client, second)["documents"])


@pytest.mark.parametrize(
    "change", ["version", "id", "false", "number", "string", "duplicate", "empty"]
)
def test_invalid_batch_never_records_partial_consent(client, change):
    headers = sign_in(client)
    body = payload(documents(client))
    if change == "version":
        body["consents"][-1]["version"] = "outdated"
    elif change == "id":
        body["consents"][-1]["document_id"] = str(uuid.uuid4())
    elif change == "false":
        body["consents"][-1]["accepted"] = False
    elif change == "number":
        body["consents"][-1]["accepted"] = 1
    elif change == "string":
        body["consents"][-1]["accepted"] = "true"
    elif change == "duplicate":
        body["consents"].append(body["consents"][0])
    else:
        body["consents"] = []
    response = client.post("/api/v1/legal/consents", headers=headers, json=body)
    assert response.status_code == (409 if change in {"version", "id"} else 422)
    assert all(not doc["accepted"] for doc in state(client, headers)["documents"])


def test_new_required_version_requires_new_consent_and_preserves_history(client):
    headers = sign_in(client)
    old_docs = documents(client)
    client.post("/api/v1/legal/consents", headers=headers, json=payload(old_docs))

    async def publish():
        async with client.db_factory() as session:
            await session.execute(
                update(LegalDocument)
                .where(LegalDocument.type == LegalDocumentType.TERMS_OF_USE)
                .values(active=False)
            )
            session.add(
                LegalDocument(
                    type=LegalDocumentType.TERMS_OF_USE,
                    version="test-next-version",
                    title="Updated terms",
                    content="Updated test text",
                    is_mandatory=True,
                    active=True,
                )
            )
            await session.commit()

    client.portal.call(publish)
    assert not state(client, headers)["all_required_accepted"]
    assert (
        client.post("/api/v1/legal/consents", headers=headers, json=payload(old_docs)).status_code
        == 409
    )
    new_docs = documents(client)
    client.post("/api/v1/legal/consents", headers=headers, json=payload(new_docs))
    assert state(client, headers)["all_required_accepted"]

    async def count():
        async with client.db_factory() as session:
            return await session.scalar(select(func.count()).select_from(UserConsent))

    assert client.portal.call(count) == 4


def test_onboarding_guard_requires_all_current_mandatory_documents(client):
    async def protected(user=Depends(require_legal_consent)):
        return {"allowed": True}

    app.add_api_route("/_test/onboarding", protected, methods=["POST"])
    route = app.routes[-1]
    try:
        headers = sign_in(client)
        assert client.post("/_test/onboarding", headers=headers).status_code == 403
        docs = documents(client)
        client.post("/api/v1/legal/consents", headers=headers, json=payload(docs[:1]))
        assert client.post("/_test/onboarding", headers=headers).status_code == 403
        client.post("/api/v1/legal/consents", headers=headers, json=payload(docs))
        assert client.post("/_test/onboarding", headers=headers).status_code == 200
        assert client.post("/_test/onboarding").status_code == 401
    finally:
        app.routes.remove(route)


def test_seed_is_idempotent_and_rejects_unversioned_text_changes(client):
    async def check():
        async with client.db_factory() as session:
            await seed_legal_documents(session, Settings().legal_documents_path)
            assert await session.scalar(select(func.count()).select_from(LegalDocument)) == 3
            row = await session.scalar(select(LegalDocument).limit(1))
            row.content = "Changed without a version increment"
            await session.commit()
        async with client.db_factory() as session:
            with pytest.raises(ValueError, match="immutable"):
                await seed_legal_documents(session, Settings().legal_documents_path)

    client.portal.call(check)
