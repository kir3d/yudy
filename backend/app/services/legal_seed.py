import json
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.models.legal import LegalDocument, LegalDocumentType


class DocumentConfig(BaseModel):
    type: LegalDocumentType
    version: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    content_file: str
    is_mandatory: bool = True


async def seed_legal_documents(session, manifest_path: Path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = [DocumentConfig.model_validate(item) for item in manifest["documents"]]
    if len(entries) != len(LegalDocumentType) or {
        item.type for item in entries if item.is_mandatory
    } != set(LegalDocumentType):
        raise ValueError("Legal manifest must include all three mandatory document types")
    for entry in entries:
        content = (manifest_path.parent / entry.content_file).read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError("Legal document content cannot be empty")
        existing = await session.scalar(
            select(LegalDocument).where(
                LegalDocument.type == entry.type, LegalDocument.version == entry.version
            )
        )
        if existing is not None and (
            existing.content != content
            or existing.title != entry.title
            or existing.is_mandatory != entry.is_mandatory
        ):
            raise ValueError("Published legal text is immutable. Increase its version.")
        await session.execute(
            update(LegalDocument)
            .where(LegalDocument.type == entry.type, LegalDocument.active.is_(True))
            .values(active=False)
        )
        if existing is None:
            session.add(
                LegalDocument(
                    type=entry.type,
                    version=entry.version,
                    title=entry.title,
                    content=content,
                    is_mandatory=entry.is_mandatory,
                    active=True,
                )
            )
        else:
            existing.active = True
        await session.flush()
    await session.commit()
