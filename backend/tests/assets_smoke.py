"""Explicit read-only HTTP smoke against local demo PostgreSQL catalog."""

import os
from decimal import Decimal

import httpx

BASE_URL = os.environ.get("ASSETS_SMOKE_URL", "http://localhost:8000") + "/api/v1/assets"


def get(path="", **params):
    response = httpx.get(BASE_URL + path, params=params, timeout=20)
    assert response.status_code == 200, response.status_code
    return response.json()


def main():
    filters = get("/filters")["data"]
    assert len(filters["regions"]) == 6
    page = get(limit=8)
    items = list(page["data"])
    while page["meta"]["next_cursor"]:
        page = get(limit=8, cursor=page["meta"]["next_cursor"])
        items.extend(page["data"])
    assert len(items) == len({item["id"] for item in items}) == 36
    assert {item["asset_type"] for item in items} == {"STOCK", "ETF"}
    assert page["meta"]["data_mode"] == "demo"
    assert get(search="aurora")["data"][0]["symbol"] == "DM01"
    assert get(search="%", limit=50)["data"] == []
    filtered = get(region="usa", sector="automotive", theme="ai_technology", asset_type="stock")[
        "data"
    ]
    assert len(filtered) == 1
    for sort, descending in (("price_asc", False), ("price_desc", True)):
        prices = [Decimal(item["price"]) for item in get(sort=sort, limit=50)["data"]]
        assert prices == sorted(prices, reverse=descending)
    cursor = get(limit=2)["meta"]["next_cursor"]
    assert (
        httpx.get(BASE_URL, params={"cursor": cursor, "region": "china"}, timeout=20).status_code
        == 400
    )
    underlying = get(search="DM01")["data"][0]
    detail = get("/" + underlying["id"])["data"]
    assert len(detail["tokens"]) == 2
    assert all(token["id"] != detail["id"] and token["availability"] for token in detail["tokens"])
    assert detail["fundamentals"]["revenue"] and detail["risks"]
    sizes = []
    for period in ("1D", "1M", "1Y", "3Y", "ALL"):
        history = get("/" + underlying["id"] + "/history", period=period)["data"]
        assert history["period"] == period
        points = history["points"]
        assert points and Decimal(points[-1]["close"]) == Decimal(underlying["price"])
        if period == "1Y":
            assert history["performance_percent"] == underlying["performance_1y"]
        sizes.append(len(points))
    assert sizes == sorted(sizes) and len(set(sizes)) == 5
    etf = get(asset_type="ETF")["data"][0]
    assert get("/" + etf["id"])["data"]["fundamentals"]["revenue"] is None
    print(
        "PASS: full demo catalog, filters, sorting, cursor pages, "
        "underlying/token details and all history periods on PostgreSQL"
    )


if __name__ == "__main__":
    main()
