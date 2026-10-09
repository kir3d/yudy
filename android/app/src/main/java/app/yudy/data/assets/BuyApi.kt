package app.yudy.data.assets

import app.yudy.BuildConfig
import app.yudy.data.auth.ApiData
import app.yudy.data.auth.SessionAuthorizer
import app.yudy.domain.assets.*
import com.squareup.moshi.Json
import javax.inject.Inject
import retrofit2.http.*

data class BuyLinkDto(val provider: String, val url: String, val external: Boolean, val demo: Boolean,
    @param:Json(name = "tokenized_asset_id") val tokenId: String,
    @param:Json(name = "token_symbol") val tokenSymbol: String)
data class BuyConfirmationDto(@param:Json(name = "event_id") val eventId: String,
    @param:Json(name = "tokenized_asset_id") val tokenId: String)
interface BuyApi {
    @GET("api/v1/assets/{id}/buy-link") suspend fun preview(@Header("Authorization") token: String, @Path("id") id: String, @Query("tokenized_asset_id") tokenId: String): ApiData<BuyLinkDto>
    @POST("api/v1/assets/{id}/buy-click") suspend fun confirm(@Header("Authorization") token: String, @Path("id") id: String, @Body body: BuyConfirmationDto): ApiData<BuyLinkDto>
}
class RemoteBuyRepository @Inject constructor(private val api: BuyApi, private val authorizer: SessionAuthorizer): BuyRepository {
    private fun checked(dto: BuyLinkDto, tokenId: String): BuyLink {
        check(dto.external && dto.tokenId == tokenId && validExternalBuyUrl(dto.url, BuildConfig.DEBUG && dto.demo)) { "Invalid provider link" }
        return BuyLink(dto.provider, dto.url, dto.tokenId, dto.tokenSymbol, dto.demo)
    }
    override suspend fun preview(assetId: String, tokenId: String) = authorizer.withAccessToken { checked(api.preview("Bearer $it", assetId, tokenId).data, tokenId) }
    override suspend fun confirm(assetId: String, tokenId: String, eventId: String) = authorizer.withAccessToken { checked(api.confirm("Bearer $it", assetId, BuyConfirmationDto(eventId, tokenId)).data, tokenId) }
}
