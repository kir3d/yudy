package app.yudy

import app.yudy.data.assets.AssetApi
import app.yudy.data.assets.RemoteAssetRepository
import app.yudy.domain.assets.CatalogQuery
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

class RemoteAssetRepositoryTest {
    private val server = MockWebServer()
    private lateinit var repository: RemoteAssetRepository
    private val summary = """{"id":"id1","symbol":"DM01","name":"Demo company","asset_type":"STOCK","sector":"Technology","industry":"Software","region":"usa","market":"usa_demo","currency":"USD","price":"25.000000","as_of":"2026-10-01T16:00:00Z","performance_1y":"5.00","has_tokenized_representation":true}"""
    private val history = """{"period":"1Y","points":[{"timestamp":"2025-10-01T16:00:00Z","close":"20.00"},{"timestamp":"2026-10-01T16:00:00Z","close":"25.00"}],"performance_percent":"25.00"}"""
    @Before fun setup() {
        server.start()
        val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
        val api = Retrofit.Builder().baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(moshi)).build().create(AssetApi::class.java)
        repository = RemoteAssetRepository(api)
    }
    @After fun cleanup() { server.shutdown() }
    private fun response(body: String) = MockResponse().setHeader("Content-Type", "application/json").setBody(body)
    @Test fun catalogPreservesDecimalsAndSendsAllFiltersWithOpaqueCursor() = runTest {
        server.enqueue(response("""{"data":[$summary],"meta":{"data_mode":"demo","total":36,"next_cursor":"next"}}"""))
        val query = CatalogQuery(" Demo ", "china", "china_demo", "Technology", "Software", "ai_technology", "STOCK", "price_desc")
        val result = repository.catalog(query, "cursor+/=")
        assertEquals("25.000000", result.items.single().price)
        assertEquals("next", result.nextCursor)
        val url = server.takeRequest().requestUrl!!
        assertEquals("Demo", url.queryParameter("search"))
        assertEquals("china", url.queryParameter("region"))
        assertEquals("china_demo", url.queryParameter("market"))
        assertEquals("Technology", url.queryParameter("sector"))
        assertEquals("Software", url.queryParameter("industry"))
        assertEquals("ai_technology", url.queryParameter("theme"))
        assertEquals("STOCK", url.queryParameter("asset_type"))
        assertEquals("price_desc", url.queryParameter("sort"))
        assertEquals("12", url.queryParameter("limit"))
        assertEquals("cursor+/=", url.queryParameter("cursor"))
    }
    @Test fun filtersUseServerOptionsAndEmptySearchIsOmitted() = runTest {
        server.enqueue(response("""{"data":{"regions":[{"code":"usa","title":"USA"}],"markets":[],"sectors":[],"industries":[],"themes":[],"asset_types":[{"code":"ETF","title":"ETF"}]}}"""))
        assertEquals("ETF", repository.filters().assetTypes.single().code)
        assertEquals("/api/v1/assets/filters", server.takeRequest().path)
        server.enqueue(response("""{"data":[],"meta":{"data_mode":"demo","total":0,"next_cursor":null}}"""))
        val page = repository.catalog(CatalogQuery())
        assertTrue(page.items.isEmpty())
        assertNull(server.takeRequest().requestUrl!!.queryParameter("search"))
    }
    @Test fun detailSeparatesTokenIssuerFromUnderlyingAssetAndNullableFundamentals() = runTest {
        val extra = """"description":"Fictional business","country":"USA","themes":[],"fundamentals":null,"risks":[{"id":"risk-id","title":"Competition","description":"Sample risk"}],"tokens":[{"id":"token-id","symbol":"DM01-TA","token_name":"Demo token","issuer":"Demo issuer","tokenization_provider":"Demo provider","backing":"Unverified demo backing","proof_of_reserves_url":null,"oracle_provider":"Synthetic feed","oracle_reference":null,"corporate_actions_info":"No payments","availability":"Demo only"}],"history":$history"""
        server.enqueue(response("""{"data":${summary.dropLast(1)},$extra}}"""))
        val detail = repository.details("id1")
        assertEquals("id1", detail.asset.id)
        assertEquals("token-id", detail.tokens.single().id)
        assertEquals("Demo issuer", detail.tokens.single().issuer)
        assertNull(detail.tokens.single().reservesUrl)
        assertNull(detail.fundamentals)
        assertEquals("1Y", detail.history.period)
        assertEquals("Competition", detail.risks.single().title)
        assertEquals("/api/v1/assets/id1", server.takeRequest().path)
    }
    @Test fun requestedHistoryPeriodAndPerformanceAreServerData() = runTest {
        server.enqueue(response("""{"data":${history.replace("1Y", "3Y")}}"""))
        val chart = repository.history("id1", "3Y")
        assertEquals("25.00", chart.performance)
        assertEquals("3Y", chart.period)
        assertEquals("3Y", server.takeRequest().requestUrl!!.queryParameter("period"))
    }
    @Test fun serverErrorsDoNotBecomeEmptyCatalogOrFakeDetails() = runTest {
        server.enqueue(MockResponse().setResponseCode(500))
        try { repository.catalog(CatalogQuery()); fail("Failure must propagate") }
        catch (error: HttpException) { assertEquals(500, error.code()) }
        server.enqueue(MockResponse().setResponseCode(404))
        try { repository.details("missing"); fail("Missing asset must propagate") }
        catch (error: HttpException) { assertEquals(404, error.code()) }
    }
}
