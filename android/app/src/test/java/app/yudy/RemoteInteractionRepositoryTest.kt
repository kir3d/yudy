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

class RemoteInteractionRepositoryTest {
    private val server = MockWebServer()
    private lateinit var repository: RemoteInteractionRepository
    @Before fun setup() {
        server.start()
        val api = Retrofit.Builder().baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()))
            .build().create(InteractionApi::class.java)
        repository = RemoteInteractionRepository(api, object: SessionAuthorizer {
            override suspend fun <T> withAccessToken(request: suspend (String) -> T) = request("session-token")
        })
    }
    @After fun cleanup() { server.shutdown() }
    private fun enqueue(body: String) { server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody(body)) }
    @Test fun explicitPostAndDeleteUseAuthenticatedStateFromServer() = runTest {
        enqueue("""{"data":{"liked":false,"disliked":false,"saved":true}}""")
        assertTrue(repository.change("one", "save", true).saved)
        val add = server.takeRequest()
        assertEquals("POST", add.method); assertEquals("/api/v1/assets/one/save", add.path)
        assertEquals("Bearer session-token", add.getHeader("Authorization"))
        enqueue("""{"data":{"liked":true,"disliked":false,"saved":false}}""")
        val result = repository.change("one", "save", false)
        assertFalse(result.saved); assertTrue(result.liked)
        val remove = server.takeRequest(); assertEquals("DELETE", remove.method)
        assertEquals("/api/v1/assets/one/save", remove.path)
    }
    @Test fun privateStateAndViewHaveSeparateEndpoints() = runTest {
        enqueue("""{"data":{"liked":true,"disliked":false,"saved":false}}""")
        assertTrue(repository.state("one").liked)
        assertEquals("/api/v1/assets/one/interactions", server.takeRequest().path)
        enqueue("""{"data":{"liked":true,"disliked":false,"saved":false}}""")
        repository.change("one", "view", true)
        assertEquals("/api/v1/assets/one/view", server.takeRequest().path)
    }
    @Test fun savedUsesPrivateEndpointAndPreservesAssetTypeAndPrice() = runTest {
        enqueue("""{"data":[{"id":"one","symbol":"ETF1","name":"Demo ETF","asset_type":"ETF","sector":null,"industry":null,"region":null,"market":null,"currency":"USD","price":"25.000000","as_of":null,"performance_1y":null,"has_tokenized_representation":false}],"meta":{"data_mode":"demo"}}""")
        val asset = repository.saved().single()
        assertEquals("ETF", asset.type); assertEquals("25.000000", asset.price)
        val request = server.takeRequest(); assertEquals("/api/v1/saved", request.path)
        assertEquals("Bearer session-token", request.getHeader("Authorization"))
    }
    @Test fun errorsNeverBecomeSuccessOrAnEmptySavedList() = runTest {
        server.enqueue(MockResponse().setResponseCode(500))
        try { repository.change("one", "like", true); fail("Must propagate") }
        catch (error: HttpException) { assertEquals(500, error.code()) }
        server.enqueue(MockResponse().setResponseCode(403))
        try { repository.saved(); fail("Must propagate") }
        catch (error: HttpException) { assertEquals(403, error.code()) }
    }
}
