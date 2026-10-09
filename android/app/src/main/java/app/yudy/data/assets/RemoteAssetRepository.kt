package app.yudy.data.assets

import app.yudy.domain.assets.AssetRepository
import app.yudy.domain.assets.CatalogQuery
import app.yudy.domain.assets.CatalogPage
import javax.inject.Inject

class RemoteAssetRepository @Inject constructor(private val api: AssetApi) : AssetRepository {
    override suspend fun filters() = api.filters().data.toDomain()
    override suspend fun catalog(query: CatalogQuery, cursor: String?): CatalogPage {
        val result = api.catalog(query.search.trim().ifEmpty { null }, query.region, query.market,
            query.sector, query.industry, query.theme, query.assetType, query.sort, 12, cursor)
        check(result.meta.dataMode == "demo") { "Unsupported market data mode" }
        return CatalogPage(result.data.map { it.summary() }, result.meta.total, result.meta.nextCursor)
    }
    override suspend fun details(id: String) = api.details(id).data.details()
    override suspend fun history(id: String, period: String) = api.history(id, period).data.toDomain()
}
