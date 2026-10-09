package app.yudy

import app.yudy.domain.assets.*
import kotlinx.coroutines.CompletableDeferred

internal fun demoAsset(id: String = "one") = AssetSummary(id, "DEMO", "Demo company", "STOCK",
    "Technology", "Software", "usa", "usa_demo", "USD", "25.00", "2026-10-01T16:00:00Z", "5.00", true)
internal fun demoHistory(period: String = "1Y") = PriceHistory(period, listOf(
    PricePoint("2025-10-01T16:00:00Z", "20.00"), PricePoint("2026-10-01T16:00:00Z", "25.00")), "25.00")
internal fun demoDetail(id: String) = AssetDetails(demoAsset(id), "A fictional demo business.", "USA",
    emptyList(), null, emptyList(), listOf(AssetRisk("Competition", "Illustrative sector risk")), demoHistory())
internal class FakeAssetRepository : AssetRepository {
    var first = CatalogPage(listOf(demoAsset()), 2, "next")
    var more = CatalogPage(listOf(demoAsset("two")), 2, null)
    var failure: Exception? = null
    var detailFailure: Exception? = null
    var historyFailure: Exception? = null
    var firstPending: CompletableDeferred<CatalogPage>? = null
    var morePending: CompletableDeferred<CatalogPage>? = null
    var detailPending: CompletableDeferred<AssetDetails>? = null
    val historyPending = mutableMapOf<String, CompletableDeferred<PriceHistory>>()
    val calls = mutableListOf<Pair<CatalogQuery, String?>>()
    override suspend fun filters() = CatalogFilters(listOf(FilterChoice("usa", "USA")), emptyList(),
        listOf(FilterChoice("Technology", "Technology")), emptyList(), emptyList(), listOf(FilterChoice("ETF", "ETF")))
    override suspend fun catalog(query: CatalogQuery, cursor: String?): CatalogPage {
        calls += query to cursor
        failure?.let { throw it }
        return (if (cursor == null) firstPending else morePending)?.await() ?: if (cursor == null) first else more
    }
    override suspend fun details(id: String): AssetDetails {
        detailFailure?.let { throw it }
        return detailPending?.await() ?: demoDetail(id)
    }
    override suspend fun history(id: String, period: String): PriceHistory {
        historyFailure?.let { throw it }
        return historyPending[period]?.await() ?: demoHistory(period)
    }
}
