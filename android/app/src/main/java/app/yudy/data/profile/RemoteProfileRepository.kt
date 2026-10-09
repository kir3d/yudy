package app.yudy.data.profile

import app.yudy.data.auth.SessionAuthorizer
import app.yudy.domain.profile.InvestorProfile
import app.yudy.domain.profile.ProfileOptions
import app.yudy.domain.profile.ProfileRepository
import javax.inject.Inject
import retrofit2.HttpException

class RemoteProfileRepository @Inject constructor(
    private val api: ProfileApi,
    private val authorizer: SessionAuthorizer,
) : ProfileRepository {
    override suspend fun options() = ProfileOptions(api.goals().data, api.interests().data, api.regions().data)
    override suspend fun load(): InvestorProfile? = try {
        authorizer.withAccessToken { api.load("Bearer $it").data.toDomain() }
    } catch (error: HttpException) {
        if (error.code() == 404) null else throw error
    }
    override suspend fun save(profile: InvestorProfile, onboarding: Boolean): InvestorProfile =
        authorizer.withAccessToken { token ->
            val body = ProfileDto.from(profile)
            (if (onboarding) api.onboarding("Bearer $token", body)
                else api.update("Bearer $token", body)).data.toDomain()
        }
}
