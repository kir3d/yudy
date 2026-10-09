from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import prevent_caching
from app.api.legal import require_legal_consent
from app.core.database import get_session
from app.repositories.risk import RiskRepository
from app.schemas.risk import AssessmentInput, QuestionsEnvelope, RiskProfileEnvelope
from app.services.risk import RiskService

router = APIRouter(prefix="/api/v1/risk", tags=["Risk"], dependencies=[Depends(prevent_caching)])


def get_risk_service(session: AsyncSession = Depends(get_session)):
    return RiskService(RiskRepository(session))


@router.get("/questions", response_model=QuestionsEnvelope)
async def questions(user=Depends(require_legal_consent), service=Depends(get_risk_service)):
    return QuestionsEnvelope(data=await service.questions(user.id))


@router.post("/assessment", response_model=RiskProfileEnvelope)
async def assessment(
    payload: AssessmentInput, user=Depends(require_legal_consent), service=Depends(get_risk_service)
):
    return RiskProfileEnvelope(data=await service.assess(user.id, payload))


@router.get("/profile", response_model=RiskProfileEnvelope)
async def profile(user=Depends(require_legal_consent), service=Depends(get_risk_service)):
    return RiskProfileEnvelope(data=await service.get(user.id))
