from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.legal import LegalDocumentType


class LegalDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    type: LegalDocumentType
    version: str
    title: str
    content: str
    is_mandatory: bool


class ConsentDocumentResponse(LegalDocumentResponse):
    accepted: bool
    accepted_at: datetime | None


class ConsentState(BaseModel):
    documents: list[ConsentDocumentResponse]
    all_required_accepted: bool


class ConsentInput(BaseModel):
    document_id: UUID
    version: str = Field(min_length=1, max_length=64)
    accepted: Literal[True]

    @field_validator("accepted", mode="before")
    @classmethod
    def explicit_acceptance(cls, value):
        if value is not True:
            raise ValueError("Explicit acceptance must be true")
        return value


class AcceptConsentsRequest(BaseModel):
    consents: list[ConsentInput] = Field(min_length=1, max_length=20)

    @field_validator("consents")
    @classmethod
    def unique_documents(cls, value):
        if len({item.document_id for item in value}) != len(value):
            raise ValueError("Document ids must be unique")
        return value


class LegalDocumentsEnvelope(BaseModel):
    data: list[LegalDocumentResponse]
    meta: dict = Field(default_factory=dict)


class ConsentStateEnvelope(BaseModel):
    data: ConsentState
    meta: dict = Field(default_factory=dict)
