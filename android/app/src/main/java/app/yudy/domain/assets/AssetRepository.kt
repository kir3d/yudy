package app.yudy.domain.assets

data class CatalogQuery(val search: String = "", val region: String? = null, val market: String? = null,
    val sector: String? = null, val industry: String? = null, val theme: String? = null,
    val assetType: String? = null, val sort: String = "symbol")
data class FilterChoice(val code: String, val title: String)
data class CatalogFilters(val regions: List<FilterChoice>, val markets: List<FilterChoice>,
    val sectors: List<FilterChoice>, val industries: List<FilterChoice>, val themes: List<FilterChoice>,
    val assetTypes: List<FilterChoice>)
data class AssetSummary(val id: String, val symbol: String, val name: String, val type: String,
    val sector: String?, val industry: String?, val region: String?, val market: String?, val currency: String,
    val price: String?, val asOf: String?, val performance1y: String?, val hasToken: Boolean)
data class CatalogPage(val items: List<AssetSummary>, val total: Int, val nextCursor: String?)
data class PricePoint(val timestamp: String, val close: String)
data class PriceHistory(val period: String, val points: List<PricePoint>, val performance: String?)
data class Fundamentals(val marketCap: String?, val pe: String?, val eps: String?, val revenue: String?,
    val revenueGrowth: String?, val netIncome: String?, val debt: String?, val cashFlow: String?,
    val dividend: String?, val dividendYield: String?, val updatedAt: String)
data class TokenInfo(val id: String, val symbol: String, val name: String, val issuer: String?,
    val provider: String?, val backing: String?, val reservesUrl: String?, val oracle: String?,
    val oracleReference: String?, val corporateActions: String?, val availability: String?)
data class AssetRisk(val title: String, val description: String)
data class AssetDetails(val asset: AssetSummary, val description: String, val country: String?,
    val themes: List<FilterChoice>, val fundamentals: Fundamentals?, val tokens: List<TokenInfo>,
    val risks: List<AssetRisk>, val history: PriceHistory)
interface AssetRepository {
    suspend fun filters(): CatalogFilters
    suspend fun catalog(query: CatalogQuery, cursor: String? = null): CatalogPage
    suspend fun details(id: String): AssetDetails
    suspend fun history(id: String, period: String): PriceHistory
}
