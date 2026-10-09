import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update

from app.models.risk import RiskAnswerOption, RiskQuestion, RiskQuestionnaire


class OptionSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1)
    score: int = Field(ge=0, le=1000, strict=True)


class QuestionSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1)
    options: list[OptionSeed] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def validate_options(self):
        if len({option.code for option in self.options}) != len(self.options):
            raise ValueError("Option codes must be unique")
        scores = [option.score for option in self.options]
        if min(scores) != 0 or max(scores) <= 0:
            raise ValueError("Every question must have zero and positive score options")
        return self


class QuestionnaireSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(min_length=1, max_length=64)
    conservative_max: int = Field(ge=0, lt=100, strict=True)
    balanced_max: int = Field(ge=0, lt=100, strict=True)
    questions: list[QuestionSeed] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_questions(self):
        if self.conservative_max >= self.balanced_max:
            raise ValueError("Category thresholds must be ordered")
        if len({question.code for question in self.questions}) != len(self.questions):
            raise ValueError("Question codes must be unique")
        return self


async def seed_risk_questionnaire(session, path):
    manifest = QuestionnaireSeed.model_validate_json(path.read_text())
    canonical = json.dumps(manifest.model_dump(), sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    existing = await session.scalar(
        select(RiskQuestionnaire).where(RiskQuestionnaire.version == manifest.version)
    )
    if existing is not None and existing.content_hash != fingerprint:
        raise ValueError("Published risk questionnaires are immutable; use a new version")
    await session.execute(
        update(RiskQuestionnaire).where(RiskQuestionnaire.active.is_(True)).values(active=False)
    )
    await session.flush()
    if existing is not None:
        existing.active = True
    else:
        questionnaire = RiskQuestionnaire(
            version=manifest.version,
            content_hash=fingerprint,
            conservative_max=manifest.conservative_max,
            balanced_max=manifest.balanced_max,
            active=True,
        )
        session.add(questionnaire)
        await session.flush()
        for order, item in enumerate(manifest.questions):
            question = RiskQuestion(
                questionnaire_id=questionnaire.id,
                code=item.code,
                text=item.text,
                sort_order=order,
                active=True,
            )
            session.add(question)
            await session.flush()
            session.add_all(
                RiskAnswerOption(
                    question_id=question.id,
                    code=option.code,
                    text=option.text,
                    score=option.score,
                    sort_order=index,
                )
                for index, option in enumerate(item.options)
            )
    await session.commit()
