from sqlalchemy import select

from app.models.auth import User
from app.models.profile import UserProfile
from app.models.risk import RiskAnswerOption, RiskProfile, RiskQuestion, RiskQuestionnaire


class RiskRepository:
    def __init__(self, session):
        self.session = session

    async def lock_user(self, user_id):
        await self.session.scalar(select(User).where(User.id == user_id).with_for_update())

    async def onboarding_complete(self, user_id):
        profile = await self.session.get(UserProfile, user_id)
        return profile is not None and profile.onboarding_completed

    async def current_questionnaire(self):
        return await self.session.scalar(
            select(RiskQuestionnaire)
            .where(RiskQuestionnaire.active.is_(True))
            .with_for_update(read=True)
        )

    async def questions(self, questionnaire_id):
        return list(
            (
                await self.session.scalars(
                    select(RiskQuestion)
                    .where(
                        RiskQuestion.questionnaire_id == questionnaire_id,
                        RiskQuestion.active.is_(True),
                    )
                    .order_by(RiskQuestion.sort_order)
                )
            ).all()
        )

    async def options(self, question_ids):
        return list(
            (
                await self.session.scalars(
                    select(RiskAnswerOption)
                    .where(RiskAnswerOption.question_id.in_(question_ids))
                    .order_by(RiskAnswerOption.sort_order)
                )
            ).all()
        )

    async def profile(self, user_id):
        return await self.session.get(RiskProfile, user_id)

    async def save(self, user_id, version, score, category, answers, calculated_at):
        profile = await self.profile(user_id)
        if profile is None:
            profile = RiskProfile(user_id=user_id)
            self.session.add(profile)
        profile.questionnaire_version = version
        profile.risk_score = score
        profile.risk_category = category
        profile.answers = answers
        profile.calculated_at = calculated_at
        await self.session.flush()
