from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BuyLink(BaseModel):
    provider: str
    url: str
    external: Literal[True] = True
    demo: Literal[True] = True
    tokenized_asset_id: UUID
    token_symbol: str


class BuyEnvelope(BaseModel):
    data: BuyLink


class BuyConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    tokenized_asset_id: UUID
