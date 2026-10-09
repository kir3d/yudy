import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, update

from app.core.config import Settings
from app.models.assets import Asset, AssetFundamentals, AssetPrice, AssetTheme, TokenizedAsset
from app.models.profile import Interest, InterestKind
from app.services.asset_seed import seed_assets


@pytest.fixture
def asset_client(client):
    async def prepare():
        async with client.db_factory() as session:
            await seed_assets(session, Settings().demo_market_path)

    client.portal.call(prepare)
    return client


def catalog(client, **params):
    response = client.get("/api/v1/assets", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_complete_demo_catalog_contains_stocks_etfs_and_public_metadata(asset_client):
    page = catalog(asset_client, limit=50)
    assert page["meta"] == {"data_mode": "demo", "total": 36, "next_cursor": None}
    assert sum(item["asset_type"] == "STOCK" for item in page["data"]) == 24
    assert sum(item["asset_type"] == "ETF" for item in page["data"]) == 12
    assert all(item["as_of"] and item["price"] and item["performance_1y"] for item in page["data"])
    assert any(item["has_tokenized_representation"] for item in page["data"])
    assert all("score" not in item for item in page["data"])


def test_cursor_pagination_has_no_duplicates_and_is_bound_to_filters(asset_client):
    first = catalog(asset_client, limit=7)
    all_ids = []
    page = first
    while True:
        all_ids.extend(item["id"] for item in page["data"])
        cursor = page["meta"]["next_cursor"]
        if cursor is None:
            break
        page = catalog(asset_client, limit=7, cursor=cursor)
    assert len(all_ids) == len(set(all_ids)) == 36
    assert (
        asset_client.get(
            "/api/v1/assets", params={"cursor": first["meta"]["next_cursor"], "region": "china"}
        ).status_code
        == 400
    )
    assert (
        asset_client.get(
            "/api/v1/assets", params={"cursor": first["meta"]["next_cursor"] + "x"}
        ).status_code
        == 400
    )
    assert asset_client.get("/api/v1/assets", params={"cursor": "not-a-cursor"}).status_code == 400


def test_search_is_case_insensitive_and_treats_wildcards_as_literal(asset_client):
    assert catalog(asset_client, search="aurora")["data"][0]["symbol"] == "DM01"
    assert catalog(asset_client, search=" dm01 ")["meta"]["total"] == 1
    assert catalog(asset_client, search="ETF")["meta"]["total"] == 12
    assert catalog(asset_client, search="%")["data"] == []
    assert catalog(asset_client, search="DM_")["data"] == []
    assert catalog(asset_client, search="unknown fictional asset")["meta"]["total"] == 0


def test_filters_combine_and_theme_mapping_uses_only_theme_interests(asset_client):
    data = catalog(
        asset_client,
        region="USA",
        sector="automotive",
        industry="electric mobility",
        market="usa_demo",
        theme="ai_technology",
        asset_type="stock",
    )["data"]
    assert len(data) == 1
    assert all(item["region"] == "usa" and item["sector"] == "Automotive" for item in data)
    assert catalog(asset_client, asset_type="etf")["meta"]["total"] == 12
    assert catalog(asset_client, theme="green_energy")["meta"]["total"] > 0
    assert catalog(asset_client, region="unknown")["data"] == []
    assert catalog(asset_client, theme="automotive")["data"] == []

    async def check():
        async with asset_client.db_factory() as session:
            kinds = (
                await session.scalars(
                    select(Interest.kind).join(AssetTheme, AssetTheme.interest_id == Interest.id)
                )
            ).all()
            assert set(kinds) == {InterestKind.THEME}

    asset_client.portal.call(check)


@pytest.mark.parametrize("sort", ["symbol", "name", "price_asc", "price_desc"])
def test_sorting_is_stable_across_pages(asset_client, sort):
    page = catalog(asset_client, sort=sort, limit=5)
    items = page["data"]
    while page["meta"]["next_cursor"]:
        page = catalog(asset_client, sort=sort, limit=5, cursor=page["meta"]["next_cursor"])
        items += page["data"]
    if sort.startswith("price"):
        values = [Decimal(item["price"]) for item in items]
        assert values == sorted(values, reverse=sort == "price_desc")
    else:
        values = [item[sort] for item in items]
        assert values == sorted(values)
    assert len({item["id"] for item in items}) == 36


def test_facets_are_loaded_from_active_catalog(asset_client):
    response = asset_client.get("/api/v1/assets/filters")
    assert response.status_code == 200
    filters = response.json()["data"]
    assert len(filters["regions"]) == 6
    assert {option["code"] for option in filters["asset_types"]} == {"STOCK", "ETF"}
    assert {option["code"] for option in filters["themes"]} == {
        "ai_technology",
        "green_energy",
        "luxury",
    }
    assert any(option["code"] == "Automotive" for option in filters["sectors"])
    assert filters["industries"] and filters["markets"]


def test_details_separate_underlying_asset_tokens_risks_and_fundamentals(asset_client):
    asset = catalog(asset_client, search="DM01")["data"][0]
    response = asset_client.get("/api/v1/assets/" + asset["id"])
    assert response.status_code == 200
    detail = response.json()["data"]
    assert detail["id"] == asset["id"]
    assert len(detail["tokens"]) == 2
    assert all(
        token["id"] != detail["id"] and token["symbol"] != detail["symbol"]
        for token in detail["tokens"]
    )
    assert all(
        token["proof_of_reserves_url"] is None and token["availability"]
        for token in detail["tokens"]
    )
    assert all("external_buy_url" not in token for token in detail["tokens"])
    assert detail["fundamentals"]["market_cap"] and detail["fundamentals"]["revenue"]
    assert detail["risks"] and "risk_category" not in detail
    assert detail["history"]["period"] == "1Y"
    assert response.json()["meta"]["data_mode"] == "demo"
    underlying_only = catalog(asset_client, search="DM02")["data"][0]
    assert (
        asset_client.get("/api/v1/assets/" + underlying_only["id"]).json()["data"]["tokens"] == []
    )


def test_all_history_periods_use_last_snapshot_and_compute_matching_change(asset_client):
    asset = catalog(asset_client, search="DM01")["data"][0]
    sizes = []
    for period in ("1D", "1M", "1Y", "3Y", "ALL"):
        response = asset_client.get(
            f"/api/v1/assets/{asset['id']}/history", params={"period": period}
        )
        assert response.status_code == 200
        history = response.json()["data"]
        assert history["period"] == period
        prices = history["points"]
        assert [point["timestamp"] for point in prices] == sorted(
            point["timestamp"] for point in prices
        )
        assert Decimal(prices[-1]["close"]) == Decimal(asset["price"])
        expected = (
            (Decimal(prices[-1]["close"]) / Decimal(prices[0]["close"]) - 1) * 100
        ).quantize(Decimal("0.01"))
        assert Decimal(history["performance_percent"]) == expected
        if period == "1Y":
            assert history["performance_percent"] == asset["performance_1y"]
        sizes.append(len(prices))
    assert sizes == sorted(sizes) and len(set(sizes)) == 5


def test_nullable_etf_fundamentals_and_missing_history_are_explicit(asset_client):
    asset = catalog(asset_client, search="DE01")["data"][0]
    detail = asset_client.get("/api/v1/assets/" + asset["id"]).json()["data"]
    assert detail["fundamentals"]["revenue"] is None

    async def remove():
        async with asset_client.db_factory() as session:
            await session.execute(
                delete(AssetPrice).where(AssetPrice.asset_id == uuid.UUID(asset["id"]))
            )
            await session.execute(
                delete(AssetFundamentals).where(
                    AssetFundamentals.asset_id == uuid.UUID(asset["id"])
                )
            )
            await session.commit()

    asset_client.portal.call(remove)
    row = catalog(asset_client, search="DE01")["data"][0]
    assert row["price"] is None and row["performance_1y"] is None and row["as_of"] is None
    detail = asset_client.get("/api/v1/assets/" + asset["id"]).json()["data"]
    assert detail["fundamentals"] is None
    assert detail["history"]["points"] == [] and detail["history"]["performance_percent"] is None
    sorted_items = catalog(asset_client, sort="price_asc", limit=50)["data"]
    assert sorted_items[-1]["id"] == asset["id"]


def test_inactive_assets_tokens_and_unknown_ids_are_not_exposed(asset_client):
    asset = catalog(asset_client, search="DM01")["data"][0]

    async def deactivate_tokens():
        async with asset_client.db_factory() as session:
            await session.execute(
                update(TokenizedAsset)
                .where(TokenizedAsset.asset_id == uuid.UUID(asset["id"]))
                .values(active=False)
            )
            await session.commit()

    asset_client.portal.call(deactivate_tokens)
    assert not catalog(asset_client, search="DM01")["data"][0]["has_tokenized_representation"]
    assert asset_client.get("/api/v1/assets/" + asset["id"]).json()["data"]["tokens"] == []

    async def deactivate_asset():
        async with asset_client.db_factory() as session:
            await session.execute(
                update(Asset).where(Asset.id == uuid.UUID(asset["id"])).values(active=False)
            )
            await session.commit()

    asset_client.portal.call(deactivate_asset)
    assert catalog(asset_client, search="DM01")["data"] == []
    for path in (asset["id"], asset["id"] + "/history", str(uuid.uuid4())):
        assert asset_client.get("/api/v1/assets/" + path).status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 51},
        {"asset_type": "bond"},
        {"sort": "unknown"},
        {"search": "a" * 101},
    ],
)
def test_invalid_catalog_parameters(client, params):
    assert client.get("/api/v1/assets", params=params).status_code == 422


def test_invalid_history_period(client):
    assert (
        client.get(
            "/api/v1/assets/" + str(uuid.uuid4()) + "/history", params={"period": "5M"}
        ).status_code
        == 422
    )


def test_seed_idempotency_preserves_asset_and_token_ids(asset_client):
    before = catalog(asset_client, limit=50)
    asset_id = before["data"][0]["id"]
    token_ids = [
        token["id"]
        for token in asset_client.get("/api/v1/assets/" + asset_id).json()["data"]["tokens"]
    ]

    async def seed():
        async with asset_client.db_factory() as session:
            before_prices = await session.scalar(select(func.count()).select_from(AssetPrice))
            await seed_assets(session, Settings().demo_market_path)
            assert await session.scalar(select(func.count()).select_from(Asset)) == 36
            assert (
                await session.scalar(select(func.count()).select_from(AssetPrice)) == before_prices
            )

    asset_client.portal.call(seed)
    assert catalog(asset_client, limit=50) == before
    assert [
        token["id"]
        for token in asset_client.get("/api/v1/assets/" + asset_id).json()["data"]["tokens"]
    ] == token_ids


def test_invalid_seed_rejects_before_modifying_data(asset_client, tmp_path):
    before = catalog(asset_client, limit=50)
    manifest = json.loads(Settings().demo_market_path.read_text())
    manifest["assets"][-1]["theme_codes"] = ["automotive"]
    path = tmp_path / "invalid-market.json"
    path.write_text(json.dumps(manifest))

    async def check():
        async with asset_client.db_factory() as session:
            with pytest.raises(ValueError, match="theme-type"):
                await seed_assets(session, path)

    asset_client.portal.call(check)
    assert catalog(asset_client, limit=50) == before
