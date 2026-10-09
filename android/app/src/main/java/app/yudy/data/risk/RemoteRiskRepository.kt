package app.yudy.data.risk

import app.yudy.data.auth.SessionAuthorizer
import app.yudy.domain.risk.RiskRepository
import javax.inject.Inject
import retrofit2.HttpException

class RemoteRiskRepository @Inject constructor(
    private val api: RiskApi,
    private val authorizer: SessionAuthorizer,
) : RiskRepository {
    override suspend fun questions() = authorizer.withAccessToken { api.questions("Bearer $it").data.toDomain() }
    override suspend fun load() = try {
        authorizer.withAccessToken { api.load("Bearer $it").data.toDomain() }
    } catch (error: HttpException) {
        if (error.code() == 404) null else throw error
    }
    override suspend fun assess(version: String, answers: Map<String, String>) = authorizer.withAccessToken {
        api.assess("Bearer $it", RiskAssessmentDto(version, answers.map { (question, option) ->
            RiskAnswerDto(question, option)
        })).data.toDomain()
    }
}
