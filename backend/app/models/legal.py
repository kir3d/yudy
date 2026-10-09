import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.auth import utcnow


class LegalDocumentType(StrEnum):
    TERMS_OF_USE = "TERMS_OF_USE"
    PRIVACY_POLICY = "PRIVACY_POLICY"
    PERSONAL_DATA_CONSENT = "PERSONAL_DATA_CONSENT"


class LegalDocument(Base):
    __tablename__ = "legal_documents"
    __table_args__ = (UniqueConstraint("type", "version", name="uq_legal_type_version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[LegalDocumentType] = mapped_column(
        Enum(
            LegalDocumentType, native_enum=False, create_constraint=True, name="legal_document_type"
        )
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


Index(
    "uq_legal_active_type",
    LegalDocument.type,
    unique=True,
    postgresql_where=LegalDocument.active.is_(True),
    sqlite_where=LegalDocument.active.is_(True),
)


class UserConsent(Base):
    __tablename__ = "user_consents"
    __table_args__ = (
        UniqueConstraint("user_id", "legal_document_id", name="uq_user_document_consent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    legal_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legal_documents.id"), nullable=False
    )
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
