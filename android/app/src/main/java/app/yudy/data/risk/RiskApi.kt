package app.yudy.data.risk

import app.yudy.data.auth.ApiData
import app.yudy.domain.risk.*
import com.squareup.moshi.Json
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

data class RiskOptionDto(val id: String, val text: String)
data class RiskQuestionDto(val id: String, val code: String, val text: String, val options: List<RiskOptionDto>)
data class RiskQuestionnaireDto(
    @param:Json(name = "questionnaire_version") val version: String,
    val questions: List<RiskQuestionDto>,
) {
    fun toDomain() = RiskQuestionnaire(version, questions.map { question ->
        RiskQuestion(question.id, question.code, question.text, question.options.map { RiskOption(it.id, it.text) })
    })
}
data class RiskResultDto(
    @param:Json(name = "risk_score") val score: Int,
    @param:Json(name = "risk_category") val category: String,
    @param:Json(name = "questionnaire_version") val version: String,
    @param:Json(name = "calculated_at") val calculatedAt: String,
    @param:Json(name = "is_current") val isCurrent: Boolean,
) {
    fun toDomain() = RiskResult(score, category, version, calculatedAt, isCurrent)
}
data class RiskAnswerDto(
    @param:Json(name = "question_id") val questionId: String,
    @param:Json(name = "option_id") val optionId: String,
)
data class RiskAssessmentDto(
    @param:Json(name = "questionnaire_version") val version: String,
    val answers: List<RiskAnswerDto>,
)
interface RiskApi {
    @GET("api/v1/risk/questions")
    suspend fun questions(@Header("Authorization") authorization: String): ApiData<RiskQuestionnaireDto>
    @GET("api/v1/risk/profile")
    suspend fun load(@Header("Authorization") authorization: String): ApiData<RiskResultDto>
    @POST("api/v1/risk/assessment")
    suspend fun assess(@Header("Authorization") authorization: String, @Body body: RiskAssessmentDto): ApiData<RiskResultDto>
}
