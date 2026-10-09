package app.yudy.data.assets

import app.yudy.data.auth.ApiData
import app.yudy.domain.assets.*
import com.squareup.moshi.Json
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

data class CatalogMetaDto(val total: Int, @param:Json(name = "next_cursor") val nextCursor: String?,
    @param:Json(name = "data_mode") val dataMode: String)
data class CatalogEnvelopeDto(val data: List<AssetDto>, val meta: CatalogMetaDto)
data class AssetDto(val id: String, val symbol: String, val name: String,
    @param:Json(name = "asset_type") val type: String, val sector: String?, val industry: String?,
    val region: String?, val market: String?, val currency: String, val price: String?,
    @param:Json(name = "as_of") val asOf: String?,
    @param:Json(name = "performance_1y") val performance1y: String?,
    @param:Json(name = "has_tokenized_representation") val hasToken: Boolean,
    val description: String? = null, val country: String? = null,
    val themes: List<FilterChoice> = emptyList(), val fundamentals: FundamentalsDto? = null,
    val tokens: List<TokenDto> = emptyList(), val risks: List<AssetRisk> = emptyList(),
    val history: HistoryDto? = null,
) {
    fun summary() = AssetSummary(id, symbol, name, type, sector, industry, region, market, currency,
        price, asOf, performance1y, hasToken)
    fun details() = AssetDetails(summary(), checkNotNull(description), country, themes,
        fundamentals?.toDomain(), tokens.map { it.toDomain() }, risks, checkNotNull(history).toDomain())
}
data class HistoryDto(val period: String, val points: List<PricePoint>,
    @param:Json(name = "performance_percent") val performance: String?) {
    fun toDomain() = PriceHistory(period, points, performance)
}
data class FundamentalsDto(
    @param:Json(name = "market_cap") val marketCap: String?, val pe: String?, val eps: String?, val revenue: String?,
    @param:Json(name = "revenue_growth") val revenueGrowth: String?,
    @param:Json(name = "net_income") val netIncome: String?, val debt: String?,
    @param:Json(name = "cash_flow") val cashFlow: String?, val dividend: String?,
    @param:Json(name = "dividend_yield") val dividendYield: String?,
    @param:Json(name = "updated_at") val updatedAt: String,
) {
    fun toDomain() = Fundamentals(marketCap, pe, eps, revenue, revenueGrowth, netIncome, debt, cashFlow,
        dividend, dividendYield, updatedAt)
}
data class TokenDto(val id: String, val symbol: String,
    @param:Json(name = "token_name") val name: String, val issuer: String?,
    @param:Json(name = "tokenization_provider") val provider: String?, val backing: String?,
    @param:Json(name = "proof_of_reserves_url") val reservesUrl: String?,
    @param:Json(name = "oracle_provider") val oracle: String?,
    @param:Json(name = "oracle_reference") val oracleReference: String?,
    @param:Json(name = "corporate_actions_info") val corporateActions: String?, val availability: String?,
) {
    fun toDomain() = TokenInfo(id, symbol, name, issuer, provider, backing, reservesUrl, oracle,
        oracleReference, corporateActions, availability)
}
data class CatalogFiltersDto(val regions: List<FilterChoice>, val markets: List<FilterChoice>,
    val sectors: List<FilterChoice>, val industries: List<FilterChoice>, val themes: List<FilterChoice>,
    @param:Json(name = "asset_types") val assetTypes: List<FilterChoice>) {
    fun toDomain() = CatalogFilters(regions, markets, sectors, industries, themes, assetTypes)
}
interface AssetApi {
    @GET("api/v1/assets/filters") suspend fun filters(): ApiData<CatalogFiltersDto>
    @GET("api/v1/assets") suspend fun catalog(@Query("search") search: String?, @Query("region") region: String?,
        @Query("market") market: String?, @Query("sector") sector: String?, @Query("industry") industry: String?,
        @Query("theme") theme: String?, @Query("asset_type") type: String?, @Query("sort") sort: String,
        @Query("limit") limit: Int, @Query("cursor") cursor: String?): CatalogEnvelopeDto
    @GET("api/v1/assets/{id}") suspend fun details(@Path("id") id: String): ApiData<AssetDto>
    @GET("api/v1/assets/{id}/history") suspend fun history(@Path("id") id: String,
        @Query("period") period: String): ApiData<HistoryDto>
}
