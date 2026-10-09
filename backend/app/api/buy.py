from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.assets import get_asset_service
from app.api.auth import prevent_caching
from app.api.legal import require_legal_consent
from app.core.config import get_settings
from app.core.database import get_session
from app.integrations.buy_provider import DemoBuyProvider
from app.repositories.buy import BuyRepository
from app.schemas.buy import BuyConfirmation, BuyEnvelope
from app.services.buy import BuyService

router = APIRouter(
    prefix="/api/v1/assets", tags=["Buy redirect"], dependencies=[Depends(prevent_caching)]
)


def get_buy_service(
    session: AsyncSession = Depends(get_session),
    assets=Depends(get_asset_service),
    settings=Depends(get_settings),
):
    return BuyService(
        BuyRepository(session),
        assets,
        DemoBuyProvider(settings.buy_provider_base_url, settings.buy_provider_name),
    )


@router.get("/{asset_id}/buy-link", response_model=BuyEnvelope)
async def link(
    asset_id: UUID,
    tokenized_asset_id: UUID,
    user=Depends(require_legal_consent),
    service=Depends(get_buy_service),
):
    return {"data": await service.link(asset_id, tokenized_asset_id)}


@router.post("/{asset_id}/buy-click", response_model=BuyEnvelope)
async def confirm(
    asset_id: UUID,
    body: BuyConfirmation,
    user=Depends(require_legal_consent),
    service=Depends(get_buy_service),
):
    return {"data": await service.confirm(user.id, asset_id, body)}
