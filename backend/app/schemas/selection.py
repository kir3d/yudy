from pydantic import BaseModel

from app.schemas.assets import AssetSummary, CatalogMeta
from app.schemas.interactions import InteractionState


class SelectionReason(BaseModel):
    type: str
    text: str


class SelectionItem(BaseModel):
    asset: AssetSummary
    interaction: InteractionState
    reasons: list[SelectionReason]


class SelectionEnvelope(BaseModel):
    data: list[SelectionItem]
    meta: CatalogMeta
