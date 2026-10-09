import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from test_legal import documents, payload, sign_in

from app.core.config import Settings, get_settings
from app.main import app
from app.models.assets import TokenizedAsset
from app.models.interactions import AssetInteraction, AssetInteractionState
from app.services.asset_seed import seed_assets
from demo_provider.app import app as demo_app


@pytest.fixture
def buy(client):
    async def seed():
        async with client.db_factory() as session:
            await seed_assets(session, Settings().demo_market_path)

    client.portal.call(seed)
    original = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_settings] = lambda: original.model_copy(
        update={"buy_provider_base_url": "http://localhost:8001", "buy_provider_name": "Test Demo"}
    )
    headers = sign_in(client)
    client.post("/api/v1/legal/consents", headers=headers, json=payload(documents(client)))
    asset = client.get("/api/v1/assets?search=DM01").json()["data"][0]
    tokens = client.get(f"/api/v1/assets/{asset['id']}").json()["data"]["tokens"]
    return client, headers, asset["id"], tokens


def preview(buy, token=None):
    client, headers, asset, tokens = buy
    return client.get(
        f"/api/v1/assets/{asset}/buy-link",
        params={"tokenized_asset_id": token or tokens[0]["id"]},
        headers=headers,
    )


def confirm(buy, event=None, token=None, **extra):
    client, headers, asset, tokens = buy
    return client.post(
        f"/api/v1/assets/{asset}/buy-click",
        headers=headers,
        json={
            "event_id": event or str(uuid.uuid4()),
            "tokenized_asset_id": token or tokens[0]["id"],
            **extra,
        },
    )


def events(client):
    async def query():
        async with client.db_factory() as session:
            return list(await session.scalars(select(AssetInteraction)))

    return client.portal.call(query)


def test_preview_is_read_only_confirmation_idempotent_no_state_changes(buy):
    client, _, asset, tokens = buy
    link = preview(buy)
    assert link.status_code == 200 and link.headers["cache-control"] == "no-store"
    data = link.json()["data"]
    assert data["external"] and data["demo"] and data["tokenized_asset_id"] == tokens[0]["id"]
    assert data["url"] == "http://localhost:8001/assets/" + tokens[0]["symbol"]
    assert events(client) == []
    event_id = str(uuid.uuid4())
    for _ in range(2):
        assert confirm(buy, event_id).json() == link.json()
    stored = events(client)
    assert len(stored) == 1 and stored[0].type == "BUY_CLICK"
    assert (
        str(stored[0].asset_id) == asset
        and stored[0].metadata_json["tokenized_asset_id"] == tokens[0]["id"]
    )

    async def states():
        async with client.db_factory() as session:
            return list(await session.scalars(select(AssetInteractionState)))

    assert client.portal.call(states) == []
    assert client.get("/api/v1/saved", headers=buy[1]).json()["data"] == []
    assert confirm(buy, event_id, token=tokens[1]["id"]).status_code == 409
    assert len(events(client)) == 1


def test_invalid_token_inactive_and_no_execution_payload(buy):
    assert preview(buy, str(uuid.uuid4())).status_code == 404
    assert confirm(buy, quantity=10, order_type="market").status_code == 422
    client, _, _, tokens = buy

    async def deactivate():
        async with client.db_factory() as session:
            await session.execute(
                update(TokenizedAsset)
                .where(TokenizedAsset.id == uuid.UUID(tokens[0]["id"]))
                .values(active=False)
            )
            await session.commit()

    client.portal.call(deactivate)
    assert preview(buy).status_code == 404 and confirm(buy).status_code == 404
    assert events(client) == []


def test_token_from_another_underlying_rejected(buy):
    client, _, _, _ = buy
    other = next(
        a
        for a in client.get("/api/v1/assets?limit=50").json()["data"]
        if a["id"] != buy[2] and a["has_tokenized_representation"]
    )
    token = client.get(f"/api/v1/assets/{other['id']}").json()["data"]["tokens"][0]["id"]
    assert confirm(buy, token=token).status_code == 404
    assert events(client) == []


def test_confirm_id_not_reusable_by_another_account(buy):
    client, _, asset, tokens = buy
    event = str(uuid.uuid4())
    assert confirm(buy, event).status_code == 200
    headers = sign_in(client, "other-buy@example.com")
    client.post("/api/v1/legal/consents", headers=headers, json=payload(documents(client)))
    assert (
        client.post(
            f"/api/v1/assets/{asset}/buy-click",
            headers=headers,
            json={"event_id": event, "tokenized_asset_id": tokens[0]["id"]},
        ).status_code
        == 409
    )
    assert len(events(client)) == 1


@pytest.mark.parametrize(
    "url",
    [
        "",
        "javascript:alert(1)",
        "https://user:secret@example.com",
        "http://localhost:99999",
        "https://example.com/#fragment",
        "http://localhost/\npath",
    ],
)
def test_unconfigured_or_unsafe_provider_never_records_click(buy, url):
    config = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_settings] = lambda: config.model_copy(
        update={"buy_provider_base_url": url}
    )
    assert preview(buy).status_code == 503 and confirm(buy).status_code == 503
    assert events(buy[0]) == []


def test_auth_and_current_consent_required(buy):
    client, _, asset, tokens = buy
    assert (
        client.get(
            f"/api/v1/assets/{asset}/buy-link", params={"tokenized_asset_id": tokens[0]["id"]}
        ).status_code
        == 401
    )
    headers = sign_in(client, "no-consent-buy@example.com")
    assert (
        client.get(
            f"/api/v1/assets/{asset}/buy-link",
            headers=headers,
            params={"tokenized_asset_id": tokens[0]["id"]},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/assets/{asset}/buy-click",
            headers=headers,
            json={"event_id": str(uuid.uuid4()), "tokenized_asset_id": tokens[0]["id"]},
        ).status_code
        == 403
    )
    assert events(client) == []


def test_independent_provider_page_has_no_transaction_endpoint():
    with TestClient(demo_app) as client:
        response = client.get("/assets/DM01-TA")
        assert response.status_code == 200 and "No transaction has been performed" in response.text
        assert "<form" not in response.text
        assert client.post("/assets/DM01-TA").status_code == 405
        assert client.post("/orders").status_code == 404
        assert client.get("/assets/%3Cscript%3E").status_code == 200
        assert "<script>" not in client.get("/assets/%3Cscript%3E").text
