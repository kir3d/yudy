from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.assets import get_asset_service
from app.api.auth import prevent_caching
from app.api.legal import require_legal_consent
from app.core.database import get_session
from app.repositories.interactions import InteractionRepository
from app.schemas.interactions import InteractionEnvelope, SavedEnvelope
from app.services.interactions import InteractionService

router = APIRouter(prefix="/api/v1", tags=["Interactions"], dependencies=[Depends(prevent_caching)])


def get_interaction_service(
    session: AsyncSession = Depends(get_session), assets=Depends(get_asset_service)
):
    return InteractionService(InteractionRepository(session), assets)


@router.get("/saved", response_model=SavedEnvelope)
async def saved(user=Depends(require_legal_consent), service=Depends(get_interaction_service)):
    return {"data": await service.saved(user.id)}


@router.get("/assets/{asset_id}/interactions", response_model=InteractionEnvelope)
async def state(
    asset_id: UUID, user=Depends(require_legal_consent), service=Depends(get_interaction_service)
):
    return {"data": await service.state(user.id, asset_id)}


@router.post("/assets/{asset_id}/{action}", response_model=InteractionEnvelope)
async def enable(
    asset_id: UUID,
    action: Literal["like", "dislike", "save", "view"],
    user=Depends(require_legal_consent),
    service=Depends(get_interaction_service),
):
    return {"data": await service.change(user.id, asset_id, action, True)}


@router.delete("/assets/{asset_id}/{action}", response_model=InteractionEnvelope)
async def disable(
    asset_id: UUID,
    action: Literal["like", "dislike", "save"],
    user=Depends(require_legal_consent),
    service=Depends(get_interaction_service),
):
    return {"data": await service.change(user.id, asset_id, action, False)}
