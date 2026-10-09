from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from js import console
from workers import fetch

from ai_privacy import private_profile_payload, safe_reason
from coingecko_snapshot import SNAPSHOT
from core import env_value
from xstocks_catalog import CATALOG


ETF_SYMBOLS = {"GLDx", "IWMx", "QQQx", "SPYx", "VTIx"}
_MARKET_CACHE: dict[str, dict[str, Any]] = {
    key: {**value, "_captured_at": SNAPSHOT["captured_at"]}
    for key, value in SNAPSHOT["markets"].items()
}
_MARKET_CACHE_AT: datetime | None = datetime.fromisoformat(SNAPSHOT["captured_at"])


def _native(value: Any) -> Any:
    return value.to_py() if hasattr(value, "to_py") else value


def _ai_response(output: Any) -> Any:
    if hasattr(output, "response"):
        return _native(output.response)
    native = _native(output)
    return native.get("response") if isinstance(native, dict) else None


async def official_catalog(request: Request) -> list[dict[str, Any]]:
    nodes = CATALOG.get("nodes", [])
    catalog = []
    for item in nodes:
        if not isinstance(item, dict) or not item.get("id") or not item.get("symbol"):
            continue
        deployments = item.get("deployments") or []
        networks = sorted(
            {
                str(deployment.get("network"))
                for deployment in deployments
                if isinstance(deployment, dict) and deployment.get("network")
            }
        )
        solana = next(
            (
                deployment
                for deployment in deployments
                if isinstance(deployment, dict) and deployment.get("network") == "Solana"
            ),
            None,
        )
        solana_usdc = next(
            (
                stablecoin
                for stablecoin in ((solana or {}).get("stablecoins") or [])
                if isinstance(stablecoin, dict) and stablecoin.get("symbol") == "USDC"
            ),
            None,
        )
        name = str(item.get("name") or item["symbol"])
        underlying = item.get("underlying") or {}
        exchange = underlying.get("exchange") or {}
        catalog.append(
            {
                "id": str(item["id"]),
                "symbol": str(item["symbol"]),
                "name": name,
                "underlying_symbol": str(item.get("underlyingSymbol") or ""),
                "asset_type": "ETF" if item["symbol"] in ETF_SYMBOLS else "STOCK",
                "currency": str(underlying.get("currency") or "USD"),
                "logo_url": str(item.get("logo") or "") or None,
                "trading_halted": bool(item.get("isTradingHalted")),
                "networks": networks,
                "description": str(item.get("description") or name),
                "underlying_isin": str(underlying.get("isin") or "") or None,
                "exchange_name": str(exchange.get("name") or "") or None,
                "exchange_code": str(exchange.get("abbreviation") or exchange.get("mic") or "") or None,
                "country": str(exchange.get("country") or "") or None,
                "solana_mint": str((solana or {}).get("address") or "") or None,
                "solana_usdc_mint": str((solana_usdc or {}).get("address") or "") or None,
            }
        )
    if not catalog:
        raise HTTPException(502, "The xStocks catalog returned no active assets")
    return catalog


async def ai_selection(
    request: Request,
    signals: dict[str, Any],
    catalog: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, str]]:
    candidates = [
        {
            "symbol": item["symbol"],
            "name": item["name"],
            "underlying_symbol": item["underlying_symbol"],
            "asset_type": item["asset_type"],
            "trading_halted": item["trading_halted"],
        }
        for item in catalog
    ]
    profile = private_profile_payload(signals)
    schema = {
        "type": "object",
        "properties": {
            "selections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["symbol", "reason"],
                },
            }
        },
        "required": ["selections"],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You rank real xStocks for educational exploration. You do not provide investment advice, "
                "predict returns, call an asset safe, or tell the user to buy. Select only exact symbols from "
                "the candidate list, exclude halted assets, use varied asset types when the profile supports it, "
                "and write one concise plain-English reason tied to the supplied profile."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {"anonymous_profile": profile, "candidates": candidates, "selection_count": limit},
                separators=(",", ":"),
            ),
        },
    ]
    model_input = {
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 900,
        "response_format": {"type": "json_schema", "json_schema": schema},
    }
    available = {item["symbol"]: item for item in catalog if not item["trading_halted"]}
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            output = await request.scope["env"].AI.run(env_value(request, "AI_MODEL"), model_input)
            response = _ai_response(output)
            if isinstance(response, str):
                response = json.loads(response)
            selections = response.get("selections") if isinstance(response, dict) else None
            if not isinstance(selections, list):
                raise ValueError("invalid structured response")
            validated: list[dict[str, str]] = []
            seen: set[str] = set()
            for item in selections:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol") or "")
                reason = safe_reason(item.get("reason"))
                if symbol in available and symbol not in seen and reason:
                    validated.append({"symbol": symbol, "reason": reason})
                    seen.add(symbol)
            if len(validated) >= limit:
                return validated[:limit]
            raise ValueError("selection could not be validated against xStocks")
        except Exception as error:
            last_error = error
            console.error("Workers AI selection attempt failed", attempt + 1, str(error))
    raise HTTPException(502, "AI selection is temporarily unavailable") from last_error


async def coingecko_markets(request: Request) -> dict[str, dict[str, Any]]:
    global _MARKET_CACHE, _MARKET_CACHE_AT
    stamp = datetime.now(timezone.utc)
    if _MARKET_CACHE_AT and (stamp - _MARKET_CACHE_AT).total_seconds() < 300:
        return _MARKET_CACHE
    base = env_value(request, "COINGECKO_API_BASE").rstrip("/")
    query = urlencode(
        {
            "vs_currency": "usd",
            "category": "xstocks-ecosystem",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": "true",
            "price_change_percentage": "24h,7d",
        }
    )
    try:
        response = await fetch(
            f"{base}/coins/markets?{query}",
            headers={"Accept": "application/json", "User-Agent": "YUDY/0.1 (+https://yudyai.xyz)"},
        )
        if response.status != 200:
            _MARKET_CACHE_AT = stamp
            return _MARKET_CACHE
        payload = _native(await response.json())
        if not isinstance(payload, list):
            _MARKET_CACHE_AT = stamp
            return _MARKET_CACHE
        parsed = {
            str(item.get("symbol") or "").casefold(): {**item, "_captured_at": stamp.isoformat()}
            for item in payload
            if isinstance(item, dict) and item.get("symbol")
        }
        if parsed:
            _MARKET_CACHE = {**_MARKET_CACHE, **parsed}
            _MARKET_CACHE_AT = stamp
    except Exception as error:
        _MARKET_CACHE_AT = stamp
        console.error("CoinGecko market snapshot failed", str(error))
    return _MARKET_CACHE


def market_fields(item: dict[str, Any] | None) -> dict[str, Any]:
    if not item:
        return {
            "sparkline_7d": [],
            "price_change_percentage_24h": None,
            "price_change_percentage_7d": None,
            "high_24h": None,
            "low_24h": None,
            "market_cap": None,
            "volume_24h": None,
            "all_time_high": None,
            "current_price": None,
            "coingecko_id": None,
            "market_data_as_of": None,
        }
    sparkline = (item.get("sparkline_in_7d") or {}).get("price") or []
    return {
        "sparkline_7d": [float(value) for value in sparkline if isinstance(value, (int, float))],
        "price_change_percentage_24h": item.get("price_change_percentage_24h_in_currency"),
        "price_change_percentage_7d": item.get("price_change_percentage_7d_in_currency"),
        "high_24h": item.get("high_24h"),
        "low_24h": item.get("low_24h"),
        "market_cap": item.get("market_cap"),
        "volume_24h": item.get("total_volume"),
        "all_time_high": item.get("ath"),
        "current_price": item.get("current_price"),
        "coingecko_id": item.get("id"),
        "market_data_as_of": item.get("_captured_at"),
    }


async def quote(request: Request, symbol: str) -> float | None:
    base = env_value(request, "XSTOCKS_API_BASE").rstrip("/")
    try:
        response = await fetch(
            f"{base}/public/assets/{symbol}/price-data",
            headers={"Accept": "application/json", "User-Agent": "YUDY/0.1 (+https://yudyai.xyz)"},
        )
        if response.status != 200:
            return None
        payload = _native(await response.json())
        value = payload.get("quote") if isinstance(payload, dict) else None
        return float(value) if value is not None else None
    except Exception:
        return None


def source_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
