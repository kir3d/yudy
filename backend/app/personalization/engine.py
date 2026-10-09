from dataclasses import dataclass
from typing import Protocol

from app.personalization.similarity import similarity


@dataclass
class RankedAsset:
    asset_id: str
    score: float
    reasons: list[dict]


class PersonalizationEngine(Protocol):
    def rank_assets(self, signals: dict, candidates: list[dict]) -> list[RankedAsset]: ...


class RuleBasedEngine:
    def __init__(self, weights):
        self.weights = weights

    def rank_assets(self, signals, candidates):
        w = self.weights
        by_id = {a["id"]: a for a in candidates}
        ranked = []
        for asset in candidates:
            contributions = []

            def add(value, kind, text):
                if value:
                    contributions.append((value, {"type": kind, "text": text}))

            def matches(interest):
                if interest["kind"] == "THEME":
                    return interest["code"] in asset["themes"]
                sector = w.sector_codes.get(interest["code"], interest["code"].replace("_", " "))
                return sector.casefold() == (asset["sector"] or "").casefold()

            for interest in signals["interests"]:
                if matches(interest):
                    add(
                        w.theme_match if interest["kind"] == "THEME" else w.sector_match,
                        "interest_match",
                        f"You selected {interest['title']} as an interest.",
                    )
            for interest in signals["excluded"]:
                if matches(interest):
                    add(
                        w.excluded_interest,
                        "excluded_interest",
                        f"Shown lower because you excluded {interest['title']}.",
                    )
            for region in signals["regions"]:
                if region["code"] == asset["region"]:
                    add(
                        w.region_match,
                        "region_match",
                        f"You selected {region['title']} as a region to explore.",
                    )
            for goal in signals["goals"]:
                if (
                    (asset["asset_type"] == "ETF" and goal["code"] in w.etf_goals)
                    or (set(asset["themes"]) & set(w.goal_themes.get(goal["code"], [])))
                    or (goal["code"] == "income" and asset["has_dividend"])
                ):
                    add(
                        w.goal_match,
                        "goal_match",
                        f"This demo example relates to your {goal['title']} exploration goal.",
                    )
            if asset["asset_type"] == "ETF":
                for field, values, weight, kind in (
                    ("experience", w.etf_experience, w.experience_match, "experience"),
                    ("horizon", w.etf_horizons, w.horizon_match, "horizon"),
                    ("risk", w.etf_risk_categories, w.risk_match, "risk_profile"),
                ):
                    if signals[field] in values:
                        add(
                            weight,
                            kind,
                            f"ETF example included using your {kind.replace('_', ' ')} response; "
                            "this is for exploration.",
                        )
            for field, direct, related, kind, label in (
                ("liked", w.liked_asset, w.liked_similar, "like", "liked"),
                ("saved", w.saved_asset, w.saved_similar, "save", "saved"),
                (
                    "disliked",
                    w.disliked_asset,
                    w.disliked_similar,
                    "dislike",
                    "marked not interested",
                ),
            ):
                sources = [
                    by_id[i]
                    for i, state in signals["states"].items()
                    if state[field] and i in by_id
                ]
                if any(a["id"] == asset["id"] for a in sources):
                    add(direct, kind, f"You {label} this asset.")
                others = [a for a in sources if a["id"] != asset["id"]]
                strength = max((similarity(asset, a) for a in others), default=0)
                add(
                    related * strength,
                    kind + "_similar",
                    f"Shares metadata with an asset you {label}.",
                )
            views = [by_id[i] for i in signals["viewed"] if i in by_id]
            strength = max((similarity(asset, a) for a in views), default=0)
            add(
                w.viewed_similar * strength,
                "view_similar",
                "Shares metadata with an asset you opened.",
            )
            score = sum(value for value, _ in contributions)
            reasons = [
                reason for _, reason in sorted(contributions, key=lambda item: -abs(item[0]))[:3]
            ]
            if not reasons:
                reasons = [
                    {
                        "type": "catalog",
                        "text": "An active demo catalog example; no matching personal signal yet.",
                    }
                ]
            ranked.append(RankedAsset(asset["id"], score, reasons))
        return sorted(
            ranked, key=lambda item: (-item.score, by_id[item.asset_id]["symbol"], item.asset_id)
        )
