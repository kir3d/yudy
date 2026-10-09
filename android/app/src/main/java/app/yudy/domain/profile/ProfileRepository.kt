package app.yudy.domain.profile

data class TaxonomyItem(val id: String, val code: String, val title: String)
data class ProfileOptions(val goals: List<TaxonomyItem>, val interests: List<TaxonomyItem>, val regions: List<TaxonomyItem>)
data class InvestorProfile(
    val experience: String = "",
    val horizon: String = "",
    val goalIds: Set<String> = emptySet(),
    val interestIds: Set<String> = emptySet(),
    val excludedInterestIds: Set<String> = emptySet(),
    val regionIds: Set<String> = emptySet(),
)
interface ProfileRepository {
    suspend fun options(): ProfileOptions
    suspend fun load(): InvestorProfile?
    suspend fun save(profile: InvestorProfile, onboarding: Boolean): InvestorProfile
}
