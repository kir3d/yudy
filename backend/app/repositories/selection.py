from fastapi import HTTPException
from sqlalchemy import select

from app.models.assets import Asset, AssetFundamentals, AssetTheme
from app.models.interactions import AssetInteraction, AssetInteractionState
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
from app.models.risk import RiskProfile, RiskQuestionnaire


class SelectionRepository:
    def __init__(self, session):
        self.session = session

    async def snapshot(self, user_id):
        profile = await self.session.get(UserProfile, user_id)
        risk = await self.session.get(RiskProfile, user_id)
        version = await self.session.scalar(
            select(RiskQuestionnaire.version).where(RiskQuestionnaire.active.is_(True))
        )
        if (
            not profile
            or not profile.onboarding_completed
            or not risk
            or risk.questionnaire_version != version
        ):
            raise HTTPException(409, "Complete onboarding and the current risk questionnaire first")

        async def choices(model, mapping, column):
            rows = await self.session.scalars(
                select(model)
                .join(mapping, model.id == column)
                .where(mapping.user_id == user_id, model.active.is_(True))
                .order_by(model.code)
            )
            return [
                {
                    "code": a.code,
                    "title": a.title,
                    **({"kind": a.kind} if isinstance(a, Interest) else {}),
                }
                for a in rows
            ]

        states = await self.session.scalars(
            select(AssetInteractionState)
            .where(AssetInteractionState.user_id == user_id)
            .order_by(AssetInteractionState.asset_id)
        )
        views = await self.session.scalars(
            select(AssetInteraction.asset_id)
            .where(AssetInteraction.user_id == user_id, AssetInteraction.type == "VIEW")
            .distinct()
            .order_by(AssetInteraction.asset_id)
        )
        signals = dict(
            experience=profile.experience,
            horizon=profile.investment_horizon,
            risk=risk.risk_category,
            interests=await choices(Interest, UserInterest, UserInterest.interest_id),
            excluded=await choices(
                Interest, UserExcludedInterest, UserExcludedInterest.interest_id
            ),
            goals=await choices(Goal, UserGoal, UserGoal.goal_id),
            regions=await choices(Region, UserRegion, UserRegion.region_id),
            states={
                str(s.asset_id): dict(liked=s.liked, disliked=s.disliked, saved=s.saved)
                for s in states
            },
            viewed=[str(v) for v in views],
        )
        assets = list(
            await self.session.scalars(
                select(Asset).where(Asset.active.is_(True)).order_by(Asset.symbol)
            )
        )
        themes = {}
        rows = await self.session.execute(
            select(AssetTheme.asset_id, Interest.code)
            .join(Interest, Interest.id == AssetTheme.interest_id)
            .where(Interest.active.is_(True))
            .order_by(Interest.code)
        )
        for asset_id, code in rows:
            themes.setdefault(str(asset_id), []).append(code)
        dividends = set(
            await self.session.scalars(
                select(AssetFundamentals.asset_id).where(AssetFundamentals.dividend > 0)
            )
        )
        candidates = [
            dict(
                id=str(a.id),
                symbol=a.symbol,
                sector=a.sector,
                industry=a.industry,
                region=a.region,
                country=a.country,
                asset_type=a.asset_type,
                themes=themes.get(str(a.id), []),
                has_dividend=a.id in dividends,
            )
            for a in assets
        ]
        return signals, candidates, assets
