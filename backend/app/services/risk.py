from fastapi import HTTPException

from app.models.auth import utcnow
from app.models.risk import RiskCategory
from app.schemas.risk import (
    AnswerOptionResponse,
    QuestionnaireResponse,
    QuestionResponse,
    RiskProfileResponse,
)
from app.services.analytics import AnalyticsService


def normalize_score(total: int, maximum: int) -> int:
    if maximum <= 0 or not 0 <= total <= maximum:
        raise ValueError("Invalid questionnaire score range")
    return (total * 200 + maximum) // (maximum * 2)


def categorize(score: int, conservative_max: int, balanced_max: int) -> RiskCategory:
    if not 0 <= score <= 100 or not 0 <= conservative_max < balanced_max < 100:
        raise ValueError("Invalid risk score or thresholds")
    if score <= conservative_max:
        return RiskCategory.CONSERVATIVE
    if score <= balanced_max:
        return RiskCategory.BALANCED
    return RiskCategory.GROWTH


class RiskService:
    def __init__(self, repository):
        self.repository = repository

    async def require_onboarding(self, user_id):
        if not await self.repository.onboarding_complete(user_id):
            raise HTTPException(403, "Complete onboarding before risk assessment")

    async def current(self):
        questionnaire = await self.repository.current_questionnaire()
        if questionnaire is None:
            raise HTTPException(503, "Risk questionnaire is unavailable")
        return questionnaire

    async def questions(self, user_id):
        await self.require_onboarding(user_id)
        questionnaire = await self.current()
        questions = await self.repository.questions(questionnaire.id)
        options = await self.repository.options([question.id for question in questions])
        if not questions or any(
            not any(option.question_id == question.id for option in options)
            for question in questions
        ):
            raise HTTPException(503, "Risk questionnaire is incomplete")
        return QuestionnaireResponse(
            questionnaire_version=questionnaire.version,
            questions=[
                QuestionResponse(
                    id=question.id,
                    code=question.code,
                    text=question.text,
                    sort_order=question.sort_order,
                    options=[
                        AnswerOptionResponse.model_validate(option)
                        for option in options
                        if option.question_id == question.id
                    ],
                )
                for question in questions
            ],
        )

    async def get(self, user_id):
        await self.require_onboarding(user_id)
        profile = await self.repository.profile(user_id)
        if profile is None:
            raise HTTPException(404, "Complete the risk questionnaire to create a risk profile")
        current = await self.current()
        return RiskProfileResponse(
            risk_score=profile.risk_score,
            risk_category=profile.risk_category,
            questionnaire_version=profile.questionnaire_version,
            calculated_at=profile.calculated_at,
            is_current=profile.questionnaire_version == current.version,
        )

    async def assess(self, user_id, payload):
        await self.repository.lock_user(user_id)
        await self.require_onboarding(user_id)
        questionnaire = await self.current()
        if payload.questionnaire_version != questionnaire.version:
            raise HTTPException(
                409, "Questionnaire was updated. Reload and answer the current version"
            )
        questions = await self.repository.questions(questionnaire.id)
        question_ids = {question.id for question in questions}
        if not question_ids or {answer.question_id for answer in payload.answers} != question_ids:
            raise HTTPException(422, "Answer every current question exactly once")
        options = await self.repository.options(question_ids)
        by_id = {option.id: option for option in options}
        total = 0
        for answer in payload.answers:
            option = by_id.get(answer.option_id)
            if option is None or option.question_id != answer.question_id:
                raise HTTPException(422, "Answer option does not belong to its question")
            total += option.score
        if any(
            not any(option.question_id == question.id for option in options)
            for question in questions
        ):
            raise HTTPException(503, "Risk questionnaire is incomplete")
        maximum = sum(
            max(option.score for option in options if option.question_id == question.id)
            for question in questions
        )
        score = normalize_score(total, maximum)
        category = categorize(score, questionnaire.conservative_max, questionnaire.balanced_max)
        calculated_at = utcnow()
        await self.repository.save(
            user_id,
            questionnaire.version,
            score,
            category,
            [answer.model_dump(mode="json") for answer in payload.answers],
            calculated_at,
        )
        AnalyticsService(self.repository.session).record(
            "risk_profile_completed", user_id, questionnaire_version=questionnaire.version
        )
        await self.repository.session.commit()
        return RiskProfileResponse(
            risk_score=score,
            risk_category=category,
            questionnaire_version=questionnaire.version,
            calculated_at=calculated_at,
            is_current=True,
        )
