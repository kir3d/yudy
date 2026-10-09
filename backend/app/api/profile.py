from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import prevent_caching
from app.api.legal import require_legal_consent
from app.core.database import get_session
from app.models.profile import Goal, Interest, Region
from app.repositories.profile import ProfileRepository
from app.schemas.profile import ProfileEnvelope, ProfileInput, TaxonomyEnvelope
from app.services.profile import ProfileService

router = APIRouter(prefix="/api/v1", tags=["Profile"], dependencies=[Depends(prevent_caching)])


def get_profile_service(session: AsyncSession = Depends(get_session)):
    return ProfileService(ProfileRepository(session))


@router.get("/goals", response_model=TaxonomyEnvelope)
async def goals(service=Depends(get_profile_service)):
    return TaxonomyEnvelope(data=await service.taxonomy(Goal))


@router.get("/interests", response_model=TaxonomyEnvelope)
async def interests(service=Depends(get_profile_service)):
    return TaxonomyEnvelope(data=await service.taxonomy(Interest))


@router.get("/regions", response_model=TaxonomyEnvelope)
async def regions(service=Depends(get_profile_service)):
    return TaxonomyEnvelope(data=await service.taxonomy(Region))


@router.get("/profile", response_model=ProfileEnvelope)
async def profile(user=Depends(require_legal_consent), service=Depends(get_profile_service)):
    return ProfileEnvelope(data=await service.get(user.id))


@router.post("/profile/onboarding", response_model=ProfileEnvelope)
async def onboarding(
    payload: ProfileInput, user=Depends(require_legal_consent), service=Depends(get_profile_service)
):
    return ProfileEnvelope(data=await service.save(user.id, payload, create=True))


@router.put("/profile", response_model=ProfileEnvelope)
async def update_profile(
    payload: ProfileInput, user=Depends(require_legal_consent), service=Depends(get_profile_service)
):
    return ProfileEnvelope(data=await service.save(user.id, payload, create=False))
