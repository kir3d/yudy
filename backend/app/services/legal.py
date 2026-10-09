from fastapi import HTTPException

from app.models.legal import LegalDocumentType, UserConsent
from app.repositories.legal import LegalRepository
from app.schemas.legal import ConsentDocumentResponse, ConsentState, LegalDocumentResponse
from app.services.analytics import AnalyticsService


class ConsentService:
    def __init__(self, repository: LegalRepository):
        self.repository = repository

    async def documents(self):
        return [
            LegalDocumentResponse.model_validate(doc)
            for doc in await self.repository.active_documents()
        ]

    async def state(self, user_id):
        documents = await self.repository.active_documents()
        accepted = {
            row.legal_document_id: row.accepted_at
            for row in await self.repository.user_consents(user_id)
        }
        mandatory_types = {doc.type for doc in documents if doc.is_mandatory}
        complete = mandatory_types == set(LegalDocumentType) and all(
            doc.id in accepted for doc in documents if doc.is_mandatory
        )
        return ConsentState(
            documents=[
                ConsentDocumentResponse(
                    **LegalDocumentResponse.model_validate(doc).model_dump(),
                    accepted=doc.id in accepted,
                    accepted_at=accepted.get(doc.id),
                )
                for doc in documents
            ],
            all_required_accepted=complete,
        )

    async def accept(self, user_id, request):
        await self.repository.lock_user(user_id)
        current = {doc.id: doc for doc in await self.repository.active_documents(lock=True)}
        for entry in request.consents:
            doc = current.get(entry.document_id)
            if doc is None or doc.version != entry.version:
                raise HTTPException(409, "Documents changed. Review the current versions.")
        existing = {row.legal_document_id for row in await self.repository.user_consents(user_id)}
        await self.repository.add_consents(
            [
                UserConsent(user_id=user_id, legal_document_id=entry.document_id)
                for entry in request.consents
                if entry.document_id not in existing
            ]
        )
        newly_accepted = [entry for entry in request.consents if entry.document_id not in existing]
        if newly_accepted:
            AnalyticsService(self.repository.session).record(
                "legal_accepted", user_id,
                documents=[{"id": str(entry.document_id), "version": entry.version}
                           for entry in newly_accepted],
            )
        await self.repository.commit()
        return await self.state(user_id)

    async def require_current_consent(self, user_id):
        if not (await self.state(user_id)).all_required_accepted:
            raise HTTPException(403, "Accept all current mandatory legal documents to continue.")
