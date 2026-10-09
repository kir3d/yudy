package app.yudy

import app.yudy.data.assets.*
import app.yudy.data.auth.SessionAuthorizer
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.*
import org.junit.*
import org.junit.Assert.*
import retrofit2.*
import retrofit2.converter.moshi.MoshiConverterFactory

class RemoteSelectionRepositoryTest {
    private val server = MockWebServer()
    private lateinit var repository: RemoteSelectionRepository
    @Before fun setup() {
        server.start()
        val api = Retrofit.Builder().baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()))
            .build().create(SelectionApi::class.java)
        repository = RemoteSelectionRepository(api, object: SessionAuthorizer {
            override suspend fun <T> withAccessToken(request: suspend (String) -> T) = request("session-token")
        })
    }
    @After fun cleanup() { server.shutdown() }
    @Test fun mapsPrivateFeedReasonsInteractionsAndOpaqueCursor() = runTest {
        server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody("""{"data":[{"asset":{"id":"one","symbol":"DM1","name":"Demo","asset_type":"STOCK","sector":null,"industry":null,"region":null,"market":null,"currency":"USD","price":"25.000000","as_of":null,"performance_1y":null,"has_tokenized_representation":false},"interaction":{"liked":false,"disliked":false,"saved":true},"reasons":[{"type":"save","text":"You saved this asset."}]}],"meta":{"data_mode":"demo","total":36,"next_cursor":"next"}}"""))
        val page = repository.feed("opaque+/=")
        assertEquals("25.000000", page.items.single().asset.price)
        assertEquals("You saved this asset.", page.items.single().reasons.single().text)
        assertTrue(page.items.single().interaction.saved); assertFalse(page.items.single().interaction.liked)
        assertEquals("next", page.nextCursor)
        val request = server.takeRequest(); assertEquals("Bearer session-token", request.getHeader("Authorization"))
        assertEquals("/api/v1/selection/for-you", request.requestUrl!!.encodedPath)
        assertEquals("opaque+/=", request.requestUrl!!.queryParameter("cursor"))
        assertEquals("12", request.requestUrl!!.queryParameter("limit"))
    }
    @Test fun cursorAndAuthorizationErrorsPropagate() = runTest {
        for(code in listOf(400, 403)) {
            server.enqueue(MockResponse().setResponseCode(code))
            try { repository.feed(); fail("Must propagate") }
            catch(error: HttpException) { assertEquals(code, error.code()) }
        }
    }

    @Test fun mapsLiveXstocksAndPrivacyBoundary() = runTest {
        server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody("""{
          "data":[{"id":"one","symbol":"AAPLx","name":"Apple xStock","underlying_symbol":"AAPL","asset_type":"STOCK","currency":"USD","price":"250.00","as_of":"2026-10-07T00:00:00Z","logo_url":"https://example.test/aapl.png","networks":["Solana"],"reason":"Matches your technology interest.","sparkline_7d":[240.0,250.0],"price_change_percentage_24h":1.25,"price_change_percentage_7d":4.16,"high_24h":252.0,"low_24h":244.0,"market_cap":12000000.0,"volume_24h":900000.0,"all_time_high":275.0,"description":"Apple xStock","underlying_isin":"US0378331005","exchange_name":"Nasdaq Stock Market","exchange_code":"NASDAQ","country":"US","coingecko_id":"apple-xstock","market_data_as_of":"2026-10-07T00:00:00Z"}],
          "meta":{"data_mode":"live_xstocks","source":"official","generated_at":"2026-10-07T00:00:00Z","privacy":{"sent_to_ai":["risk_category"],"never_sent":["email","user_id"]}}
        }"""))
        val result = repository.xstocks()
        assertEquals("AAPLx", result.items.single().symbol)
        assertEquals("Matches your technology interest.", result.items.single().reason)
        assertEquals(listOf(240.0, 250.0), result.items.single().sparkline7d)
        assertEquals("2026-10-07T00:00:00Z", result.items.single().marketDataAsOf)
        assertEquals(4.16, result.items.single().priceChangePercentage7d!!, 0.001)
        assertEquals("US0378331005", result.items.single().underlyingIsin)
        assertEquals("apple-xstock", result.items.single().coingeckoId)
        assertEquals(listOf("email", "user_id"), result.neverSent)
        val request = server.takeRequest()
        assertEquals("/api/v1/selection/xstocks", request.requestUrl!!.encodedPath)
        assertEquals("Bearer session-token", request.getHeader("Authorization"))
        assertEquals("8", request.requestUrl!!.queryParameter("limit"))
    }

    @Test fun mapsCatalogInteractionsSavedVenuesAndBuyTracking() = runTest {
        val item = """{"id":"one","symbol":"SPYx","name":"SPDR S&P 500 ETF xStock","underlying_symbol":"SPY","asset_type":"ETF","currency":"USD","price":"680.00","as_of":"2026-10-09T00:00:00Z","logo_url":"https://example.test/spy.png","networks":["Solana"],"reason":"Available for exploration.","interaction":{"liked":false,"disliked":true,"saved":true}}"""
        server.enqueue(MockResponse().setHeader("Content-Type", "application/json")
            .setBody("""{"data":[$item],"meta":{"total":1,"next_cursor":null}}"""))
        server.enqueue(MockResponse().setHeader("Content-Type", "application/json")
            .setBody("""{"data":{"liked":true,"disliked":false,"saved":true}}"""))
        server.enqueue(MockResponse().setHeader("Content-Type", "application/json")
            .setBody("""{"data":[{"name":"Kraken","kind":"CEX","url":"https://kraken.test/spyx","network":null}]}"""))
        server.enqueue(MockResponse().setResponseCode(204))

        val page = repository.catalog("SPY", "ETF", "price_desc")
        assertEquals("SPYx", page.items.single().symbol)
        assertTrue(page.items.single().interaction.disliked)
        assertEquals("ETF", page.items.single().assetType)
        val catalogRequest = server.takeRequest()
        assertEquals("/api/v1/xstocks", catalogRequest.requestUrl!!.encodedPath)
        assertEquals("SPY", catalogRequest.requestUrl!!.queryParameter("search"))
        assertEquals("ETF", catalogRequest.requestUrl!!.queryParameter("asset_type"))

        assertTrue(repository.changeXstock("one", "like", true).liked)
        assertEquals("POST", server.takeRequest().method)
        assertEquals("Kraken", repository.venues("one").single().name)
        assertEquals("/api/v1/xstocks/one/venues", server.takeRequest().requestUrl!!.encodedPath)
        repository.recordBuy("one", "Kraken")
        val buy = server.takeRequest()
        assertEquals("/api/v1/xstocks/one/buy-click", buy.requestUrl!!.encodedPath)
        assertTrue(buy.body.readUtf8().contains("Kraken"))
    }
}
