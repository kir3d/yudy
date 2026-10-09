from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.profile import Experience, Horizon


class TaxonomyItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    title: str


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experience: Experience
    investment_horizon: Horizon
    goal_ids: list[UUID] = Field(min_length=1, max_length=50)
    interest_ids: list[UUID] = Field(default_factory=list, max_length=50)
    excluded_interest_ids: list[UUID] = Field(default_factory=list, max_length=50)
    region_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @field_validator("goal_ids", "interest_ids", "excluded_interest_ids", "region_ids")
    @classmethod
    def unique_ids(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Selections must be unique")
        return value

    @model_validator(mode="after")
    def disjoint_interests(self):
        if set(self.interest_ids) & set(self.excluded_interest_ids):
            raise ValueError("Interests and exclusions must not overlap")
        return self


class ProfileResponse(ProfileInput):
    onboarding_completed: bool


class ProfileEnvelope(BaseModel):
    data: ProfileResponse
    meta: dict = Field(default_factory=dict)


class TaxonomyEnvelope(BaseModel):
    data: list[TaxonomyItem]
    meta: dict = Field(default_factory=dict)
