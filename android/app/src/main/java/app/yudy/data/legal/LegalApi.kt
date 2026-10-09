package app.yudy.data.legal

import app.yudy.data.auth.ApiData
import com.squareup.moshi.Json
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

data class ConsentDocumentDto(
    val id: String,
    val type: String,
    val version: String,
    val title: String,
    val content: String,
    @param:Json(name = "is_mandatory") val mandatory: Boolean,
    val accepted: Boolean,
    @param:Json(name = "accepted_at") val acceptedAt: String?,
)
data class ConsentSnapshotDto(
    val documents: List<ConsentDocumentDto>,
    @param:Json(name = "all_required_accepted") val allRequiredAccepted: Boolean,
)
data class ConsentInputDto(
    @param:Json(name = "document_id") val documentId: String,
    val version: String,
    val accepted: Boolean = true,
)
data class AcceptConsentsDto(val consents: List<ConsentInputDto>)

interface LegalApi {
    @GET("api/v1/legal/consents/me")
    suspend fun load(@Header("Authorization") authorization: String): ApiData<ConsentSnapshotDto>
    @POST("api/v1/legal/consents")
    suspend fun accept(@Header("Authorization") authorization: String,
        @Body body: AcceptConsentsDto): ApiData<ConsentSnapshotDto>
}
