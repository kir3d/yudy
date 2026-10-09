package app.yudy.data.assets

import app.yudy.data.auth.SessionAuthorizer
import app.yudy.domain.assets.*
import com.squareup.moshi.Json
import javax.inject.Inject
import retrofit2.http.*

data class SelectionItemDto(val asset: AssetDto, val interaction: InteractionState, val reasons: List<SelectionReason>)
data class SelectionEnvelopeDto(val data: List<SelectionItemDto>, val meta: CatalogMetaDto)
data class XStockSuggestionDto(
    val id: String,
    val symbol: String,
    val name: String,
    @Json(name = "underlying_symbol") val underlyingSymbol: String,
    @Json(name = "asset_type") val assetType: String,
    val currency: String,
    val price: String?,
    @Json(name = "as_of") val asOf: String,
    @Json(name = "logo_url") val logoUrl: String?,
    val networks: List<String>,
    val reason: String,
    @Json(name = "sparkline_7d") val sparkline7d: List<Double> = emptyList(),
    @Json(name = "price_change_percentage_24h") val priceChangePercentage24h: Double? = null,
    @Json(name = "price_change_percentage_7d") val priceChangePercentage7d: Double? = null,
    @Json(name = "high_24h") val high24h: Double? = null,
    @Json(name = "low_24h") val low24h: Double? = null,
    @Json(name = "market_cap") val marketCap: Double? = null,
    @Json(name = "volume_24h") val volume24h: Double? = null,
    @Json(name = "all_time_high") val allTimeHigh: Double? = null,
    val description: String = "",
    @Json(name = "underlying_isin") val underlyingIsin: String? = null,
    @Json(name = "exchange_name") val exchangeName: String? = null,
    @Json(name = "exchange_code") val exchangeCode: String? = null,
    val country: String? = null,
    @Json(name = "coingecko_id") val coingeckoId: String? = null,
    @Json(name = "market_data_as_of") val marketDataAsOf: String? = null,
    val interaction: InteractionState = InteractionState(),
) {
    fun toDomain() = XStockSuggestion(
        id = id, symbol = symbol, name = name, underlyingSymbol = underlyingSymbol,
        assetType = assetType, currency = currency, price = price, asOf = asOf,
        logoUrl = logoUrl, networks = networks, reason = reason, sparkline7d = sparkline7d,
        priceChangePercentage24h = priceChangePercentage24h,
        priceChangePercentage7d = priceChangePercentage7d, high24h = high24h,
        low24h = low24h, marketCap = marketCap, volume24h = volume24h,
        allTimeHigh = allTimeHigh, description = description, underlyingIsin = underlyingIsin,
        exchangeName = exchangeName, exchangeCode = exchangeCode, country = country,
        coingeckoId = coingeckoId, marketDataAsOf = marketDataAsOf,
        interaction = interaction,
    )
}
data class XStockPrivacyDto(
    @Json(name = "sent_to_ai") val sentToAi: List<String>,
    @Json(name = "never_sent") val neverSent: List<String>,
)
data class XStockMetaDto(
    @Json(name = "data_mode") val dataMode: String,
    val source: String,
    @Json(name = "generated_at") val generatedAt: String,
    val privacy: XStockPrivacyDto,
)
data class XStockEnvelopeDto(val data: List<XStockSuggestionDto>, val meta: XStockMetaDto)
data class XStockListMetaDto(
    val total: Int,
    @Json(name = "next_cursor") val nextCursor: String? = null,
)
data class XStockListEnvelopeDto(val data: List<XStockSuggestionDto>, val meta: XStockListMetaDto)
data class InteractionEnvelopeDto(val data: InteractionState)
data class XStockVenueDto(val name: String, val kind: String, val url: String, val network: String?) {
    fun toDomain() = XStockVenue(name, kind, url, network)
}
data class XStockVenueEnvelopeDto(val data: List<XStockVenueDto>)
interface SelectionApi {
    @GET("api/v1/selection/for-you") suspend fun feed(@Header("Authorization") token: String, @Query("limit") limit: Int, @Query("cursor") cursor: String?): SelectionEnvelopeDto
    @GET("api/v1/selection/xstocks") suspend fun xstocks(@Header("Authorization") token: String, @Query("limit") limit: Int): XStockEnvelopeDto
    @GET("api/v1/xstocks") suspend fun catalog(
        @Header("Authorization") token: String,
        @Query("search") search: String?,
        @Query("asset_type") assetType: String?,
        @Query("sort") sort: String,
        @Query("limit") limit: Int,
        @Query("cursor") cursor: String?,
    ): XStockListEnvelopeDto
    @GET("api/v1/xstocks/saved") suspend fun saved(
        @Header("Authorization") token: String,
    ): XStockListEnvelopeDto
    @POST("api/v1/xstocks/{id}/{action}") suspend fun enable(
        @Header("Authorization") token: String,
        @Path("id") id: String,
        @Path("action") action: String,
    ): InteractionEnvelopeDto
    @DELETE("api/v1/xstocks/{id}/{action}") suspend fun disable(
        @Header("Authorization") token: String,
        @Path("id") id: String,
        @Path("action") action: String,
    ): InteractionEnvelopeDto
    @GET("api/v1/xstocks/{id}/venues") suspend fun venues(
        @Header("Authorization") token: String,
        @Path("id") id: String,
    ): XStockVenueEnvelopeDto
    @POST("api/v1/xstocks/{id}/buy-click") suspend fun buyClick(
        @Header("Authorization") token: String,
        @Path("id") id: String,
        @Body payload: Map<String, String>,
    ): retrofit2.Response<Unit>
}
class RemoteSelectionRepository @Inject constructor(private val api: SelectionApi, private val authorizer: SessionAuthorizer): SelectionRepository {
    override suspend fun feed(cursor: String?) = authorizer.withAccessToken {
        val response = api.feed("Bearer $it", 12, cursor)
        check(response.meta.dataMode == "demo")
        SelectionPage(response.data.map { item -> SelectionItem(item.asset.summary(), item.interaction, item.reasons) }, response.meta.total, response.meta.nextCursor)
    }
    override suspend fun xstocks(forceRefresh: Boolean) = authorizer.withAccessToken {
        val response = api.xstocks("Bearer $it", 8)
        check(response.meta.dataMode == "live_xstocks")
        XStockSelection(response.data.map(XStockSuggestionDto::toDomain), response.meta.source,
            response.meta.generatedAt, response.meta.privacy.sentToAi, response.meta.privacy.neverSent)
    }
    override suspend fun catalog(search: String?, assetType: String?, sort: String, cursor: String?) =
        authorizer.withAccessToken {
            val response = api.catalog("Bearer $it", search, assetType, sort, 50, cursor)
            XStockPage(response.data.map(XStockSuggestionDto::toDomain), response.meta.total,
                response.meta.nextCursor)
        }
    override suspend fun savedXstocks() = authorizer.withAccessToken {
        api.saved("Bearer $it").data.map(XStockSuggestionDto::toDomain)
    }
    override suspend fun changeXstock(id: String, action: String, active: Boolean) =
        authorizer.withAccessToken {
            if (active) api.enable("Bearer $it", id, action).data
            else api.disable("Bearer $it", id, action).data
        }
    override suspend fun venues(id: String) = authorizer.withAccessToken {
        api.venues("Bearer $it", id).data.map(XStockVenueDto::toDomain)
    }
    override suspend fun recordBuy(id: String, venue: String) = authorizer.withAccessToken {
        val response = api.buyClick("Bearer $it", id, mapOf("venue" to venue))
        check(response.isSuccessful)
    }
}
