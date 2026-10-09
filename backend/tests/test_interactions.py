import uuid

import pytest
from sqlalchemy import select, update
from test_legal import documents, payload, sign_in

from app.core.config import Settings
from app.models.assets import Asset
from app.models.interactions import AssetInteraction
from app.services.asset_seed import seed_assets


@pytest.fixture
def context(client):
    async def seed():
        async with client.db_factory() as session:
            await seed_assets(session, Settings().demo_market_path)

    client.portal.call(seed)
    headers = sign_in(client)
    client.post("/api/v1/legal/consents", headers=headers, json=payload(documents(client)))
    assets = client.get("/api/v1/assets?limit=50").json()["data"]
    return client, headers, assets


def act(context, action, method="post", index=0):
    client, headers, assets = context
    response = getattr(client, method)(
        f"/api/v1/assets/{assets[index]['id']}/{action}", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def saved(context):
    client, headers, _ = context
    return client.get("/api/v1/saved", headers=headers).json()["data"]


def test_like_and_view_never_save(context):
    assert act(context, "view") == dict(liked=False, disliked=False, saved=False)
    assert act(context, "like") == dict(liked=True, disliked=False, saved=False)
    assert saved(context) == []
    assert act(context, "like", "delete")["liked"] is False


def test_save_is_independent_and_explicit(context):
    assert act(context, "save") == dict(liked=False, disliked=False, saved=True)
    assert len(saved(context)) == 1
    assert act(context, "like")["saved"]
    assert act(context, "dislike") == dict(liked=False, disliked=True, saved=True)
    assert act(context, "dislike", "delete") == dict(liked=False, disliked=False, saved=True)
    assert len(saved(context)) == 1
    assert act(context, "save", "delete")["saved"] is False
    assert saved(context) == []


def test_mutual_exclusion_and_idempotent_history(context):
    act(context, "dislike")
    act(context, "dislike")
    act(context, "like")
    act(context, "like")
    act(context, "save", "delete")
    client, headers, assets = context
    current = client.get(f"/api/v1/assets/{assets[0]['id']}/interactions", headers=headers)
    assert current.json()["data"] == dict(liked=True, disliked=False, saved=False)

    async def history():
        async with client.db_factory() as session:
            return list(await session.scalars(select(AssetInteraction)))

    events = client.portal.call(history)
    assert sorted(e.type for e in events) == ["DISLIKE", "LIKE", "REMOVE_DISLIKE"]
    assert all(e.created_at and e.user_id and e.asset_id for e in events)


def test_private_saved_isolated_and_groups_preserved(context):
    client, headers, assets = context
    stock = next(i for i, a in enumerate(assets) if a["asset_type"] == "STOCK")
    etf = next(i for i, a in enumerate(assets) if a["asset_type"] == "ETF")
    act(context, "save", index=stock)
    act(context, "save", index=etf)
    assert {a["asset_type"] for a in saved(context)} == {"STOCK", "ETF"}
    second = sign_in(client, "other@example.com")
    client.post("/api/v1/legal/consents", headers=second, json=payload(documents(client)))
    assert client.get("/api/v1/saved", headers=second).json()["data"] == []
    assert not client.get(
        f"/api/v1/assets/{assets[stock]['id']}/interactions", headers=second
    ).json()["data"]["saved"]


def test_unknown_and_inactive_asset_no_events(context):
    client, headers, assets = context
    assert client.post(f"/api/v1/assets/{uuid.uuid4()}/save", headers=headers).status_code == 404
    act(context, "save")

    async def deactivate():
        async with client.db_factory() as session:
            await session.execute(
                update(Asset).where(Asset.id == uuid.UUID(assets[0]["id"])).values(active=False)
            )
            await session.commit()

    client.portal.call(deactivate)
    assert saved(context) == []
    assert client.post(f"/api/v1/assets/{assets[0]['id']}/like", headers=headers).status_code == 404


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/v1/saved", "get"),
        ("/api/v1/assets/{id}/interactions", "get"),
        ("/api/v1/assets/{id}/save", "post"),
        ("/api/v1/assets/{id}/like", "delete"),
        ("/api/v1/assets/{id}/view", "post"),
    ],
)
def test_auth_and_consent_required(context, path, method):
    client, _, assets = context
    path = path.format(id=assets[0]["id"])
    assert getattr(client, method)(path).status_code == 401
    headers = sign_in(client, "unaccepted@example.com")
    assert getattr(client, method)(path, headers=headers).status_code == 403
