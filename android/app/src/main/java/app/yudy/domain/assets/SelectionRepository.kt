package app.yudy.domain.assets

data class SelectionReason(val type: String, val text: String)
data class SelectionItem(val asset: AssetSummary, val interaction: InteractionState, val reasons: List<SelectionReason>)
data class SelectionPage(val items: List<SelectionItem>, val total: Int, val nextCursor: String?)
data class XStockSuggestion(
    val id: String,
    val symbol: String,
    val name: String,
    val underlyingSymbol: String,
    val assetType: String,
    val currency: String,
    val price: String?,
    val asOf: String,
    val logoUrl: String?,
    val networks: List<String>,
    val reason: String,
    val sparkline7d: List<Double> = emptyList(),
    val priceChangePercentage24h: Double? = null,
    val priceChangePercentage7d: Double? = null,
    val high24h: Double? = null,
    val low24h: Double? = null,
    val marketCap: Double? = null,
    val volume24h: Double? = null,
    val allTimeHigh: Double? = null,
    val description: String = "",
    val underlyingIsin: String? = null,
    val exchangeName: String? = null,
    val exchangeCode: String? = null,
    val country: String? = null,
    val coingeckoId: String? = null,
    val marketDataAsOf: String? = null,
    val interaction: InteractionState = InteractionState(),
)
data class XStockSelection(
    val items: List<XStockSuggestion>,
    val source: String,
    val generatedAt: String,
    val sentToAi: List<String>,
    val neverSent: List<String>,
)
data class XStockPage(val items: List<XStockSuggestion>, val total: Int, val nextCursor: String?)
data class XStockVenue(
    val name: String,
    val kind: String,
    val url: String,
    val network: String?,
)
interface SelectionRepository {
    suspend fun feed(cursor: String? = null): SelectionPage
    suspend fun xstocks(forceRefresh: Boolean = false): XStockSelection
    suspend fun catalog(
        search: String? = null,
        assetType: String? = null,
        sort: String = "symbol",
        cursor: String? = null,
    ): XStockPage
    suspend fun savedXstocks(): List<XStockSuggestion>
    suspend fun changeXstock(id: String, action: String, active: Boolean): InteractionState
    suspend fun venues(id: String): List<XStockVenue>
    suspend fun recordBuy(id: String, venue: String)
}
