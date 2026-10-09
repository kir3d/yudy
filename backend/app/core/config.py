from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.personalization.weights import RankingWeights


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    personalization_weights: RankingWeights = Field(default_factory=RankingWeights)
    personalization_cache_seconds: int = Field(default=120, ge=1, le=3600)
    learn_articles_path: Path = Path(__file__).resolve().parents[2] / "learn" / "manifest.json"
    buy_provider_base_url: str = ""
    buy_provider_name: str = "Demo Provider"
    app_env: str = "development"
    cors_origins: list[str] = Field(default_factory=list)
    database_url: str = ""
    redis_url: str = ""
    jwt_secret: str = ""
    jwt_issuer: str = "yudy"
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_days: int = Field(default=30, ge=1, le=90)
    auth_rate_limit: int = Field(default=20, ge=1)
    auth_rate_window_seconds: int = Field(default=60, ge=1)
    risk_questionnaire_path: Path = Path(__file__).resolve().parents[2] / "risk" / "manifest.json"
    demo_market_path: Path = Path(__file__).resolve().parents[2] / "market" / "manifest.json"
    taxonomy_path: Path = Path(__file__).resolve().parents[2] / "taxonomy" / "manifest.json"
    legal_documents_path: Path = Path(__file__).resolve().parents[2] / "legal" / "manifest.json"

    @field_validator("cors_origins")
    @classmethod
    def explicit_origins(cls, origins):
        for origin in origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username or parsed.password or parsed.path or parsed.query
                    or parsed.fragment or "*" in origin or "\\" in origin
                    or any(c.isspace() for c in origin)):
                raise ValueError("CORS origins must be explicit http(s) origins without paths")
            _ = parsed.port
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
