from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.assets import get_asset_service
from app.api.auth import prevent_caching
from app.api.legal import require_legal_consent
from app.core.config import get_settings
from app.core.database import get_session
from app.personalization.engine import RuleBasedEngine
from app.repositories.selection import SelectionRepository
from app.schemas.selection import SelectionEnvelope
from app.services.selection import SelectionService

router = APIRouter(
    prefix="/api/v1/selection", tags=["Selection"], dependencies=[Depends(prevent_caching)]
)


def get_selection_service(
    request: Request,
    session: AsyncSession = Depends(get_session),
    assets=Depends(get_asset_service),
    settings=Depends(get_settings),
):
    return SelectionService(
        SelectionRepository(session),
        assets,
        RuleBasedEngine(settings.personalization_weights),
        request.app.state.redis,
        settings.personalization_cache_seconds,
        settings.personalization_weights.model_dump(),
    )


@router.get("/for-you", response_model=SelectionEnvelope)
async def for_you(
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    user=Depends(require_legal_consent),
    service=Depends(get_selection_service),
):
    return await service.feed(user.id, limit, cursor)
