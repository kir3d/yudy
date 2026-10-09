from fastapi import HTTPException

from app.models.auth import utcnow
from app.models.profile import (
    Goal,
    Interest,
    Region,
    UserExcludedInterest,
    UserGoal,
    UserInterest,
    UserProfile,
    UserRegion,
)
from app.schemas.profile import ProfileResponse, TaxonomyItem
from app.services.analytics import AnalyticsService

SELECTIONS = (
    ("goal_ids", Goal, UserGoal, UserGoal.goal_id),
    ("interest_ids", Interest, UserInterest, UserInterest.interest_id),
    ("excluded_interest_ids", Interest, UserExcludedInterest, UserExcludedInterest.interest_id),
    ("region_ids", Region, UserRegion, UserRegion.region_id),
)


class ProfileService:
    def __init__(self, repository):
        self.repository = repository

    async def taxonomy(self, model):
        return [TaxonomyItem.model_validate(item) for item in await self.repository.taxonomy(model)]

    async def get(self, user_id):
        await self.repository.lock_user(user_id)
        profile = await self.repository.profile(user_id)
        if profile is None:
            raise HTTPException(404, "Complete onboarding to create your profile")
        selections = {
            name: await self.repository.selections(mapping, column, user_id)
            for name, _, mapping, column in SELECTIONS
        }
        return ProfileResponse(
            experience=profile.experience,
            investment_horizon=profile.investment_horizon,
            onboarding_completed=profile.onboarding_completed,
            **selections,
        )

    async def save(self, user_id, payload, create):
        await self.repository.lock_user(user_id)
        profile = await self.repository.profile(user_id)
        if profile is None and not create:
            raise HTTPException(404, "Profile does not exist")
        for name, taxonomy, _, _ in SELECTIONS:
            valid = {item.id for item in await self.repository.taxonomy(taxonomy)}
            if not set(getattr(payload, name)) <= valid:
                raise HTTPException(422, f"Unknown or inactive selection in {name}")
        first_completion = profile is None or not profile.onboarding_completed
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self.repository.session.add(profile)
        profile.experience = payload.experience
        profile.investment_horizon = payload.investment_horizon
        profile.onboarding_completed = True
        profile.updated_at = utcnow()
        for name, _, mapping, column in SELECTIONS:
            await self.repository.replace(mapping, column, user_id, getattr(payload, name))
        if first_completion:
            AnalyticsService(self.repository.session).record("onboarding_completed", user_id)
        await self.repository.session.commit()
        return ProfileResponse(
            experience=payload.experience,
            investment_horizon=payload.investment_horizon,
            onboarding_completed=True,
            **{name: sorted(getattr(payload, name)) for name, _, _, _ in SELECTIONS},
        )
