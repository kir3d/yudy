package app.yudy

import app.yudy.data.auth.SessionAuthorizer
import app.yudy.data.profile.ProfileApi
import app.yudy.data.profile.RemoteProfileRepository
import app.yudy.domain.profile.InvestorProfile
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

class RemoteProfileRepositoryTest {
    private val server = MockWebServer()
    private lateinit var repository: RemoteProfileRepository
    private val profileJson = """{"data":{"experience":"NEW","investment_horizon":"FIVE_PLUS","goal_ids":["goal"],"interest_ids":["ai"],"excluded_interest_ids":["oil"],"region_ids":["usa"],"onboarding_completed":true}}"""
    @Before fun setup() {
        server.start()
        val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
        val api = Retrofit.Builder().baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(moshi)).build().create(ProfileApi::class.java)
        repository = RemoteProfileRepository(api, object : SessionAuthorizer {
            override suspend fun <T> withAccessToken(request: suspend (String) -> T) = request("test-token")
        })
    }
    @After fun cleanup() { server.shutdown() }
    private fun response(body: String = profileJson) = MockResponse().setHeader("Content-Type", "application/json").setBody(body)
    @Test fun optionsUseServerTaxonomy() = runTest {
        repeat(3) { server.enqueue(response("""{"data":[{"id":"id","code":"code","title":"Title"}]}""")) }
        val options = repository.options()
        assertEquals("Title", options.goals.single().title)
        assertEquals("/api/v1/goals", server.takeRequest().path)
        assertEquals("/api/v1/interests", server.takeRequest().path)
        assertEquals("/api/v1/regions", server.takeRequest().path)
    }
    @Test fun missingProfileStartsOnboardingButConsentFailurePropagates() = runTest {
        server.enqueue(MockResponse().setResponseCode(404))
        assertNull(repository.load())
        server.enqueue(MockResponse().setResponseCode(403))
        try { repository.load(); fail("Consent failure must propagate") }
        catch (error: HttpException) { assertEquals(403, error.code()) }
    }
    @Test fun saveSendsSeparateSelectionsAndUpdateUsesPut() = runTest {
        val profile = InvestorProfile("NEW", "FIVE_PLUS", setOf("goal"), setOf("ai"), setOf("oil"), setOf("usa"))
        server.enqueue(response())
        assertEquals(profile, repository.save(profile, true))
        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertEquals("/api/v1/profile/onboarding", request.path)
        assertEquals("Bearer test-token", request.getHeader("Authorization"))
        val body = request.body.readUtf8()
        assertTrue(body.contains("\"excluded_interest_ids\":[\"oil\"]"))
        assertTrue(body.contains("\"investment_horizon\":\"FIVE_PLUS\""))
        assertFalse(body.contains("user_id"))
        server.enqueue(response())
        repository.save(profile, false)
        val update = server.takeRequest()
        assertEquals("PUT", update.method)
        assertEquals("/api/v1/profile", update.path)
    }
}
