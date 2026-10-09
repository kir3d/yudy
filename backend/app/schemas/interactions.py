from pydantic import BaseModel, ConfigDict

from app.schemas.assets import AssetSummary, DemoMeta


class InteractionState(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    liked: bool = False
    disliked: bool = False
    saved: bool = False


class InteractionEnvelope(BaseModel):
    data: InteractionState


class SavedEnvelope(BaseModel):
    data: list[AssetSummary]
    meta: DemoMeta = DemoMeta()
