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

class RemoteBuyRepositoryTest {
    private val server = MockWebServer()
    private lateinit var repository: RemoteBuyRepository
    private val response = """{"data":{"provider":"Demo","url":"https://example.test/assets/TOKEN","external":true,"demo":true,"tokenized_asset_id":"token","token_symbol":"TOKEN"}}"""
    @Before fun setup() {
        server.start()
        val api = Retrofit.Builder().baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()))
            .build().create(BuyApi::class.java)
        repository = RemoteBuyRepository(api, object: SessionAuthorizer {
            override suspend fun <T> withAccessToken(request: suspend (String) -> T) = request("session-token")
        })
    }
    @After fun cleanup() { server.shutdown() }
    @Test fun previewIsGetAndConfirmationOnlySendsTokenAndIdempotencyId() = runTest {
        server.enqueue(MockResponse().setBody(response)); assertTrue(repository.preview("asset", "token").demo)
        val preview = server.takeRequest(); assertEquals("GET", preview.method)
        assertEquals("token", preview.requestUrl!!.queryParameter("tokenized_asset_id"))
        assertEquals("Bearer session-token", preview.getHeader("Authorization"))
        server.enqueue(MockResponse().setBody(response)); assertEquals("TOKEN", repository.confirm("asset", "token", "event").tokenSymbol)
        val confirm = server.takeRequest(); assertEquals("POST", confirm.method); assertEquals("/api/v1/assets/asset/buy-click", confirm.path)
        val body = confirm.body.readUtf8(); assertTrue(body.contains("\"event_id\":\"event\"")); assertTrue(body.contains("\"tokenized_asset_id\":\"token\""))
        assertFalse(body.contains("quantity")); assertFalse(body.contains("user_id")); assertFalse(body.contains("url"))
    }
    @Test fun unsafeAndWrongTokenResponsesNeverReachLauncher() = runTest {
        for(body in listOf(response.replace("https://example.test/assets/TOKEN", "javascript:alert(1)"), response.replace("\"external\":true", "\"external\":false"), response.replace("\"token\"", "\"other\""))) {
            server.enqueue(MockResponse().setBody(body))
            try { repository.preview("asset", "token"); fail("Must reject") } catch(expected: IllegalStateException) { }
        }
    }
    @Test fun httpErrorsPropagate() = runTest {
        server.enqueue(MockResponse().setResponseCode(503))
        try { repository.preview("asset", "token"); fail("Must propagate") } catch(error: HttpException) { assertEquals(503, error.code()) }
    }
}
