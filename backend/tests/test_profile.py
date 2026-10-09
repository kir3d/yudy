import uuid

import pytest
from sqlalchemy import func, select, update

from app.core.config import Settings
from app.models.legal import LegalDocument, LegalDocumentType
from app.models.profile import Goal, Interest, Region, UserGoal, UserProfile
from app.services.taxonomy_seed import seed_taxonomy


def account(client, email="profile@example.com", consent=True):
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "profile-password-42"}
    )
    assert response.status_code == 201
    headers = {"Authorization": "Bearer " + response.json()["data"]["access_token"]}
    if consent:
        documents = client.get("/api/v1/legal/documents").json()["data"]
        response = client.post(
            "/api/v1/legal/consents",
            headers=headers,
            json={
                "consents": [
                    {"document_id": doc["id"], "version": doc["version"], "accepted": True}
                    for doc in documents
                ]
            },
        )
        assert response.status_code == 200
    return headers


def body(client):
    def ids(name):
        response = client.get("/api/v1/" + name)
        assert response.status_code == 200
        return [item["id"] for item in response.json()["data"]]

    interests = ids("interests")
    return {
        "experience": "SOME",
        "investment_horizon": "FIVE_PLUS",
        "goal_ids": ids("goals")[:2],
        "interest_ids": interests[:2],
        "excluded_interest_ids": interests[2:3],
        "region_ids": ids("regions")[:2],
    }


def test_real_profile_routes_require_current_consent(client):
    headers = account(client, consent=False)
    payload = body(client)
    for method, path in (("get", "/profile"), ("post", "/profile/onboarding"), ("put", "/profile")):
        kwargs = {} if method == "get" else {"json": payload}
        assert (
            getattr(client, method)("/api/v1" + path, headers=headers, **kwargs).status_code == 403
        )
        assert getattr(client, method)("/api/v1" + path, **kwargs).status_code == 401


def test_onboarding_persists_idempotently_and_update_replaces_selections(client):
    headers = account(client)
    payload = body(client)
    assert client.get("/api/v1/profile", headers=headers).status_code == 404
    assert client.put("/api/v1/profile", headers=headers, json=payload).status_code == 404
    for _ in range(2):
        response = client.post("/api/v1/profile/onboarding", headers=headers, json=payload)
        assert response.status_code == 200
        assert response.json()["data"]["onboarding_completed"]
    assert client.get("/api/v1/profile", headers=headers).json() == response.json()
    payload.update(
        experience="NEW",
        goal_ids=payload["goal_ids"][:1],
        interest_ids=[],
        excluded_interest_ids=[],
        region_ids=[],
    )
    updated = client.put("/api/v1/profile", headers=headers, json=payload)
    assert updated.status_code == 200
    assert updated.json()["data"] == {**payload, "onboarding_completed": True}
    assert client.get("/api/v1/profile", headers=headers).json() == updated.json()

    async def counts():
        async with client.db_factory() as session:
            assert await session.scalar(select(func.count()).select_from(UserProfile)) == 1
            assert await session.scalar(select(func.count()).select_from(UserGoal)) == 1

    client.portal.call(counts)


def test_profiles_do_not_leak_or_update_other_accounts(client):
    first = account(client)
    second = account(client, "second@example.com")
    payload = body(client)
    client.post("/api/v1/profile/onboarding", headers=first, json=payload)
    assert client.get("/api/v1/profile", headers=second).status_code == 404
    payload["experience"] = "EXPERIENCED"
    client.post("/api/v1/profile/onboarding", headers=second, json=payload)
    assert client.get("/api/v1/profile", headers=first).json()["data"]["experience"] == "SOME"


@pytest.mark.parametrize(
    "change",
    ["unknown", "inactive", "duplicate", "overlap", "empty", "experience", "horizon", "user_id"],
)
def test_invalid_update_is_atomic(client, change):
    headers = account(client)
    original = body(client)
    before = client.post("/api/v1/profile/onboarding", headers=headers, json=original).json()
    payload = {**original, "experience": "NEW"}
    if change == "unknown":
        payload["region_ids"] = [str(uuid.uuid4())]
    elif change == "inactive":

        async def deactivate():
            async with client.db_factory() as session:
                await session.execute(
                    update(Interest)
                    .where(Interest.id == uuid.UUID(original["interest_ids"][0]))
                    .values(active=False)
                )
                await session.commit()

        client.portal.call(deactivate)
    elif change == "duplicate":
        payload["goal_ids"] = original["goal_ids"] * 2
    elif change == "overlap":
        payload["excluded_interest_ids"] = original["interest_ids"]
    elif change == "empty":
        payload["goal_ids"] = []
    elif change in {"experience", "horizon"}:
        payload["experience" if change == "experience" else "investment_horizon"] = "INVALID"
    else:
        payload["user_id"] = str(uuid.uuid4())
    assert client.put("/api/v1/profile", headers=headers, json=payload).status_code == 422
    assert client.get("/api/v1/profile", headers=headers).json() == before


def test_updated_legal_version_blocks_existing_profile_until_accepted(client):
    headers = account(client)
    payload = body(client)
    assert (
        client.post("/api/v1/profile/onboarding", headers=headers, json=payload).status_code == 200
    )

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
                    version="profile-test-v2",
                    title="New terms",
                    content="New terms text",
                    is_mandatory=True,
                    active=True,
                )
            )
            await session.commit()

    client.portal.call(publish)
    assert client.get("/api/v1/profile", headers=headers).status_code == 403
    assert client.put("/api/v1/profile", headers=headers, json=payload).status_code == 403
    documents = client.get("/api/v1/legal/documents").json()["data"]
    client.post(
        "/api/v1/legal/consents",
        headers=headers,
        json={
            "consents": [
                {"document_id": doc["id"], "version": doc["version"], "accepted": True}
                for doc in documents
            ]
        },
    )
    assert client.get("/api/v1/profile", headers=headers).status_code == 200


def test_taxonomy_seed_is_idempotent_and_inactive_items_are_hidden(client):
    async def seed():
        async with client.db_factory() as session:
            await seed_taxonomy(session, Settings().taxonomy_path)
            assert await session.scalar(select(func.count()).select_from(Goal)) == 5
            assert await session.scalar(select(func.count()).select_from(Interest)) == 12
            assert await session.scalar(select(func.count()).select_from(Region)) == 6
            await session.execute(update(Goal).where(Goal.code == "income").values(active=False))
            await session.commit()

    client.portal.call(seed)
    goals = client.get("/api/v1/goals").json()["data"]
    assert len(goals) == 4
    assert all(item["code"] != "income" for item in goals)
