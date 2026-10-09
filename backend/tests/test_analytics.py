import uuid
from collections import Counter

import pytest
from sqlalchemy import select
from test_legal import documents, payload, sign_in
from test_profile import body
from test_risk import answers, questionnaire

from app.core.config import Settings, get_settings
from app.main import app
from app.models.analytics import AnalyticsEvent
from app.models.auth import User
from app.models.interactions import AssetInteraction
from app.services.analytics import AnalyticsService
from app.services.asset_seed import seed_assets
from app.services.learn_seed import seed_articles


def events(client):
    async def query():
        async with client.db_factory() as session:
            return list(await session.scalars(select(AnalyticsEvent)))

    return client.portal.call(query)


@pytest.fixture
def tracked(client):
    async def seed():
        async with client.db_factory() as session:
            await seed_assets(session, Settings().demo_market_path)
            await seed_articles(session, Settings().learn_articles_path)

    client.portal.call(seed)
    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"buy_provider_base_url": "http://localhost:8001"}
    )
    headers = sign_in(client)
    return client, headers


def consent(client, headers):
    response = client.post(
        "/api/v1/legal/consents", headers=headers, json=payload(documents(client))
    )
    assert response.status_code == 200


def test_lifecycle_is_server_owned_and_retries_do_not_repeat_milestones(tracked):
    client, headers = tracked
    for _ in range(2):
        consent(client, headers)
        assert client.post(
            "/api/v1/profile/onboarding", headers=headers, json=body(client)
        ).status_code == 200
    assert client.put("/api/v1/profile", headers=headers, json=body(client)).status_code == 200
    questions = questionnaire(client, headers)
    for choice in (0, 3):
        assert client.post(
            "/api/v1/risk/assessment", headers=headers, json=answers(questions, choice)
        ).status_code == 200
    rows = events(client)
    assert Counter(row.event_name for row in rows) == {
        "registration_completed": 1, "legal_accepted": 1,
        "onboarding_completed": 1, "risk_profile_completed": 2,
    }
    user_id = client.get("/api/v1/users/me", headers=headers).json()["data"]["id"]
    assert all(str(row.user_id) == user_id and row.created_at for row in rows)
    assert len({row.id for row in rows}) == len(rows)
    legal = next(row for row in rows if row.event_name == "legal_accepted")
    assert len(legal.properties["documents"]) == 3
    assert all(set(doc) == {"id", "version"} for doc in legal.properties["documents"])
    risk = [row for row in rows if row.event_name == "risk_profile_completed"]
    assert all(row.properties == {"questionnaire_version": questions["questionnaire_version"]}
               for row in risk)


def test_interactions_count_transitions_keep_save_independent_and_buy_idempotent(tracked):
    client, headers = tracked
    consent(client, headers)
    asset = client.get("/api/v1/assets?search=DM01").json()["data"][0]
    path = "/api/v1/assets/" + asset["id"]
    for action in ("view", "view", "like", "like", "save", "save", "dislike", "dislike"):
        assert client.post(path + "/" + action, headers=headers).status_code == 200
    for _ in range(2):
        assert client.delete(path + "/save", headers=headers).status_code == 200
    token = client.get(path).json()["data"]["tokens"][0]
    assert client.get(path + "/buy-link", headers=headers,
                      params={"tokenized_asset_id": token["id"]}).status_code == 200
    assert not any(row.event_name == "buy_clicked" for row in events(client))
    event_id = str(uuid.uuid4())
    for _ in range(2):
        assert client.post(path + "/buy-click", headers=headers, json={
            "event_id": event_id, "tokenized_asset_id": token["id"]
        }).status_code == 200
    rows = [row for row in events(client) if row.event_name.startswith(("asset_", "buy_"))]
    assert Counter(row.event_name for row in rows) == {
        "asset_viewed": 2, "asset_liked": 1, "asset_disliked": 1,
        "asset_saved": 1, "asset_unsaved": 1, "buy_clicked": 1,
    }
    assert all(row.properties["asset_id"] == asset["id"] for row in rows)
    buy = next(row for row in rows if row.event_name == "buy_clicked")
    assert buy.properties["interaction_id"] == event_id
    assert buy.properties["tokenized_asset_id"] == token["id"] and buy.properties["demo"]


def test_public_learn_tracks_successful_detail_requests_only(tracked):
    client, _ = tracked
    items = client.get("/api/v1/learn/articles").json()["data"]
    assert not any(row.event_name == "learn_article_opened" for row in events(client))
    for _ in range(2):
        assert client.get("/api/v1/learn/articles/" + items[0]["slug"]).status_code == 200
    assert client.get("/api/v1/learn/articles/missing").status_code == 404
    rows = [row for row in events(client) if row.event_name == "learn_article_opened"]
    assert len(rows) == 2 and all(row.user_id is None for row in rows)
    assert all(row.properties == {"article_id": items[0]["id"], "slug": items[0]["slug"]}
               for row in rows)
    assert client.get("/api/v1/analytics").status_code == 404
    assert client.post("/api/v1/analytics", json={"event_name": "asset_liked"}).status_code == 404


def test_rejected_requests_do_not_record_success(tracked):
    client, headers = tracked
    before = len(events(client))
    assert client.post("/api/v1/auth/register", json={
        "email": "legal@example.com", "password": "a-password-long-enough"
    }).status_code == 409
    assert client.post("/api/v1/assets/" + str(uuid.uuid4()) + "/like",
                       headers=headers).status_code == 403
    stale = payload(documents(client))
    stale["consents"][0]["version"] = "outdated"
    assert client.post("/api/v1/legal/consents", headers=headers, json=stale).status_code == 409
    assert len(events(client)) == before


def test_analytics_failure_rolls_back_domain_mutation(tracked, monkeypatch):
    client, headers = tracked
    consent(client, headers)
    asset = client.get("/api/v1/assets?search=DM01").json()["data"][0]
    path = "/api/v1/assets/" + asset["id"]
    before = len(events(client))

    def fail(*args, **kwargs):
        raise RuntimeError("test analytics failure")

    monkeypatch.setattr(AnalyticsService, "record", fail)
    assert client.post(path + "/like", headers=headers).status_code == 500
    assert not client.get(path + "/interactions", headers=headers).json()["data"]["liked"]
    assert len(events(client)) == before

    async def query():
        async with client.db_factory() as session:
            assert list(await session.scalars(select(AssetInteraction))) == []

    client.portal.call(query)


def test_registration_event_failure_does_not_leave_account(client, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("test analytics failure")

    monkeypatch.setattr(AnalyticsService, "record", fail)
    assert client.post("/api/v1/auth/register", json={
        "email": "failure@example.com", "password": "test-password-42"
    }).status_code == 500

    async def query():
        async with client.db_factory() as session:
            assert list(await session.scalars(select(User))) == []

    client.portal.call(query)
    assert events(client) == []


@pytest.mark.parametrize("event", [
    "legal_accepted", "onboarding_completed", "risk_profile_completed", "buy_clicked",
])
def test_failure_rolls_back_each_transaction_boundary(tracked, monkeypatch, event):
    client, headers = tracked
    if event != "legal_accepted":
        consent(client, headers)
    if event == "risk_profile_completed":
        assert client.post("/api/v1/profile/onboarding", headers=headers,
                           json=body(client)).status_code == 200
    before = len(events(client))
    original = AnalyticsService.record

    def fail(self, name, *args, **kwargs):
        if name == event:
            raise RuntimeError("test transaction failure")
        return original(self, name, *args, **kwargs)

    monkeypatch.setattr(AnalyticsService, "record", fail)
    if event == "legal_accepted":
        response = client.post("/api/v1/legal/consents", headers=headers,
                               json=payload(documents(client)))
    elif event == "onboarding_completed":
        response = client.post("/api/v1/profile/onboarding", headers=headers, json=body(client))
    elif event == "risk_profile_completed":
        response = client.post("/api/v1/risk/assessment", headers=headers,
                               json=answers(questionnaire(client, headers)))
    else:
        asset = client.get("/api/v1/assets?search=DM01").json()["data"][0]
        path = "/api/v1/assets/" + asset["id"]
        token = client.get(path).json()["data"]["tokens"][0]
        response = client.post(path + "/buy-click", headers=headers, json={
            "event_id": str(uuid.uuid4()), "tokenized_asset_id": token["id"]
        })
    assert response.status_code == 500
    assert len(events(client)) == before
    if event == "legal_accepted":
        state = client.get("/api/v1/legal/consents/me", headers=headers).json()["data"]
        assert not state["all_required_accepted"]
    elif event == "onboarding_completed":
        assert client.get("/api/v1/profile", headers=headers).status_code == 404
    elif event == "risk_profile_completed":
        assert client.get("/api/v1/risk/profile", headers=headers).status_code == 404
    else:
        async def query():
            async with client.db_factory() as session:
                assert list(await session.scalars(select(AssetInteraction))) == []

        client.portal.call(query)


@pytest.mark.parametrize("name,properties", [
    ("unknown_event", {}), ("registration_completed", {"email": "private@example.test"}),
    ("risk_profile_completed", {"answers": []}), ("asset_liked", {}),
])
def test_internal_service_rejects_unknown_properties(client, name, properties):
    async def check():
        async with client.db_factory() as session:
            with pytest.raises(ValueError):
                AnalyticsService(session).record(name, **properties)
            await session.commit()

    client.portal.call(check)
    assert events(client) == []
