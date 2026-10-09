from typing import Protocol
from urllib.parse import quote, urlsplit

from fastapi import HTTPException

from app.schemas.buy import BuyLink


class BuyProvider(Protocol):
    async def get_buy_link(self, token) -> BuyLink: ...


class DemoBuyProvider:
    def __init__(self, base_url, name):
        self.base_url = base_url
        self.name = name

    async def get_buy_link(self, token):
        try:
            url = urlsplit(self.base_url)
            valid = (
                url.scheme in ("http", "https")
                and url.hostname
                and not (url.username or url.password or url.query or url.fragment)
                and url.port != 0
            )
        except ValueError:
            valid = False
        if (
            not valid
            or not self.name.strip()
            or any(ord(c) <= 32 for c in self.base_url)
            or "\\" in self.base_url
        ):
            raise HTTPException(503, "Demo provider is not configured")
        return BuyLink(
            provider=self.name,
            url=self.base_url.rstrip("/") + "/assets/" + quote(token.symbol, safe=""),
            tokenized_asset_id=token.id,
            token_symbol=token.symbol,
        )
