from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, prevent_caching
from app.core.database import get_session
from app.repositories.legal import LegalRepository
from app.schemas.legal import AcceptConsentsRequest, ConsentStateEnvelope, LegalDocumentsEnvelope
from app.services.legal import ConsentService

router = APIRouter(prefix="/api/v1/legal", tags=["Legal"], dependencies=[Depends(prevent_caching)])


def get_consent_service(session: AsyncSession = Depends(get_session)):
    return ConsentService(LegalRepository(session))


async def require_legal_consent(
    user=Depends(get_current_user), service: ConsentService = Depends(get_consent_service)
):
    """Dependency for onboarding routes introduced in Phase 4."""
    await service.require_current_consent(user.id)
    return user


@router.get("/documents", response_model=LegalDocumentsEnvelope)
async def documents(service: ConsentService = Depends(get_consent_service)):
    return {"data": await service.documents()}


@router.get("/consents/me", response_model=ConsentStateEnvelope)
async def consent_state(
    user=Depends(get_current_user), service: ConsentService = Depends(get_consent_service)
):
    return {"data": await service.state(user.id)}


@router.post("/consents", response_model=ConsentStateEnvelope)
async def accept_consents(
    body: AcceptConsentsRequest,
    user=Depends(get_current_user),
    service: ConsentService = Depends(get_consent_service),
):
    return {"data": await service.accept(user.id, body)}
