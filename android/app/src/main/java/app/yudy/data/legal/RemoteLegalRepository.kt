package app.yudy.data.legal

import app.yudy.data.auth.SessionAuthorizer
import app.yudy.domain.legal.ConsentSnapshot
import app.yudy.domain.legal.LegalDocument
import app.yudy.domain.legal.LegalRepository
import javax.inject.Inject

class RemoteLegalRepository @Inject constructor(
    private val api: LegalApi,
    private val authorizer: SessionAuthorizer,
) : LegalRepository {
    private fun ConsentSnapshotDto.toDomain() = ConsentSnapshot(documents.map {
        LegalDocument(it.id, it.type, it.version, it.title, it.content, it.mandatory,
            it.accepted, it.acceptedAt)
    }, allRequiredAccepted)

    override suspend fun load(): ConsentSnapshot = authorizer.withAccessToken { token ->
        api.load("Bearer $token").data.toDomain()
    }

    override suspend fun accept(documents: List<LegalDocument>): ConsentSnapshot =
        authorizer.withAccessToken { token ->
            api.accept("Bearer $token", AcceptConsentsDto(documents.map {
                ConsentInputDto(it.id, it.version)
            })).data.toDomain()
        }
}
