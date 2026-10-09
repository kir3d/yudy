from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.risk import RiskCategory


class AnswerOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    text: str
    sort_order: int


class QuestionResponse(BaseModel):
    id: UUID
    code: str
    text: str
    sort_order: int
    options: list[AnswerOptionResponse]


class QuestionnaireResponse(BaseModel):
    questionnaire_version: str
    questions: list[QuestionResponse]


class RiskAnswerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: UUID
    option_id: UUID


class AssessmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    questionnaire_version: str = Field(min_length=1, max_length=64)
    answers: list[RiskAnswerInput] = Field(min_length=1, max_length=100)

    @field_validator("answers")
    @classmethod
    def unique_questions(cls, value):
        if len({item.question_id for item in value}) != len(value):
            raise ValueError("Answer each question once")
        return value


class RiskProfileResponse(BaseModel):
    risk_score: int
    risk_category: RiskCategory
    questionnaire_version: str
    calculated_at: datetime
    is_current: bool


class QuestionsEnvelope(BaseModel):
    data: QuestionnaireResponse
    meta: dict = Field(default_factory=dict)


class RiskProfileEnvelope(BaseModel):
    data: RiskProfileResponse
    meta: dict = Field(default_factory=dict)
