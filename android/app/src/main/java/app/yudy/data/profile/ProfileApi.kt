package app.yudy.data.profile

import app.yudy.data.auth.ApiData
import app.yudy.domain.profile.InvestorProfile
import app.yudy.domain.profile.TaxonomyItem
import com.squareup.moshi.Json
import retrofit2.http.*

data class ProfileDto(
    val experience: String,
    @param:Json(name = "investment_horizon") val horizon: String,
    @param:Json(name = "goal_ids") val goalIds: List<String>,
    @param:Json(name = "interest_ids") val interestIds: List<String>,
    @param:Json(name = "excluded_interest_ids") val excludedInterestIds: List<String>,
    @param:Json(name = "region_ids") val regionIds: List<String>,
) {
    fun toDomain() = InvestorProfile(experience, horizon, goalIds.toSet(), interestIds.toSet(),
        excludedInterestIds.toSet(), regionIds.toSet())
    companion object {
        fun from(profile: InvestorProfile) = ProfileDto(profile.experience, profile.horizon,
            profile.goalIds.toList(), profile.interestIds.toList(), profile.excludedInterestIds.toList(),
            profile.regionIds.toList())
    }
}
interface ProfileApi {
    @GET("api/v1/goals") suspend fun goals(): ApiData<List<TaxonomyItem>>
    @GET("api/v1/interests") suspend fun interests(): ApiData<List<TaxonomyItem>>
    @GET("api/v1/regions") suspend fun regions(): ApiData<List<TaxonomyItem>>
    @GET("api/v1/profile") suspend fun load(@Header("Authorization") authorization: String): ApiData<ProfileDto>
    @POST("api/v1/profile/onboarding") suspend fun onboarding(@Header("Authorization") authorization: String,
        @Body profile: ProfileDto): ApiData<ProfileDto>
    @PUT("api/v1/profile") suspend fun update(@Header("Authorization") authorization: String,
        @Body profile: ProfileDto): ApiData<ProfileDto>
}
