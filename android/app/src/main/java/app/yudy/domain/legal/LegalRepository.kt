package app.yudy.domain.legal

data class LegalDocument(
    val id: String,
    val type: String,
    val version: String,
    val title: String,
    val content: String,
    val mandatory: Boolean,
    val accepted: Boolean,
    val acceptedAt: String?,
)

data class ConsentSnapshot(val documents: List<LegalDocument>, val allRequiredAccepted: Boolean)

interface LegalRepository {
    suspend fun load(): ConsentSnapshot
    suspend fun accept(documents: List<LegalDocument>): ConsentSnapshot
}
