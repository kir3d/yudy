from pydantic import BaseModel, ConfigDict, Field


class RankingWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    sector_match: float = Field(default=30, ge=0)
    theme_match: float = Field(default=30, ge=0)
    region_match: float = Field(default=15, ge=0)
    goal_match: float = Field(default=10, ge=0)
    experience_match: float = Field(default=2, ge=0)
    horizon_match: float = Field(default=2, ge=0)
    risk_match: float = Field(default=2, ge=0)
    liked_asset: float = Field(default=8, ge=0)
    saved_asset: float = Field(default=6, ge=0)
    liked_similar: float = Field(default=5, ge=0)
    saved_similar: float = Field(default=3, ge=0)
    viewed_similar: float = Field(default=1, ge=0)
    excluded_interest: float = Field(default=-40, le=0)
    disliked_asset: float = Field(default=-60, le=0)
    disliked_similar: float = Field(default=-30, le=0)
    sector_codes: dict[str, str] = Field(default_factory=lambda: {"oil_gas": "Oil & Gas"})
    goal_themes: dict[str, list[str]] = Field(
        default_factory=lambda: {"growth": ["ai_technology", "green_energy"]}
    )
    etf_goals: list[str] = Field(default_factory=lambda: ["diversification"])
    etf_experience: list[str] = Field(default_factory=lambda: ["NEW"])
    etf_horizons: list[str] = Field(default_factory=lambda: ["FIVE_PLUS"])
    etf_risk_categories: list[str] = Field(default_factory=lambda: ["Conservative"])
