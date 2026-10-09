package app.yudy

import app.yudy.data.auth.SessionAuthorizer
import app.yudy.data.risk.RiskApi
import app.yudy.data.risk.RemoteRiskRepository
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

class RemoteRiskRepositoryTest {
    private val server = MockWebServer()
    private lateinit var repository: RemoteRiskRepository
    private val resultJson = """{"data":{"risk_score":48,"risk_category":"Balanced","questionnaire_version":"v2","calculated_at":"2026-10-04T10:00:00Z","is_current":true}}"""
    @Before fun setup() {
        server.start()
        val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
        val api = Retrofit.Builder().baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(moshi)).build().create(RiskApi::class.java)
        repository = RemoteRiskRepository(api, object : SessionAuthorizer {
            override suspend fun <T> withAccessToken(request: suspend (String) -> T) = request("test-token")
        })
    }
    @After fun cleanup() { server.shutdown() }
    private fun response(body: String) = MockResponse().setHeader("Content-Type", "application/json").setBody(body)
    @Test fun questionnaireMapsServerTextVersionAndOptionIds() = runTest {
        server.enqueue(response("""{"data":{"questionnaire_version":"v2","questions":[{"id":"q1","code":"volatility","text":"How do you feel?","sort_order":0,"options":[{"id":"a1","text":"Comfortable","sort_order":0}]}]}}"""))
        val questions = repository.questions()
        assertEquals("v2", questions.version)
        assertEquals("Comfortable", questions.questions.single().options.single().text)
        val request = server.takeRequest()
        assertEquals("/api/v1/risk/questions", request.path)
        assertEquals("Bearer test-token", request.getHeader("Authorization"))
    }
    @Test fun onlyMissingProfileMapsToNull() = runTest {
        server.enqueue(MockResponse().setResponseCode(404))
        assertNull(repository.load())
        server.enqueue(MockResponse().setResponseCode(403))
        try { repository.load(); fail("Legal restriction must propagate") }
        catch (error: HttpException) { assertEquals(403, error.code()) }
    }
    @Test fun assessmentSendsVersionAndAnswerIdsAndUsesServerResult() = runTest {
        server.enqueue(response(resultJson))
        val result = repository.assess("v2", mapOf("q1" to "a1"))
        assertEquals(48, result.score)
        assertEquals("Balanced", result.category)
        assertTrue(result.isCurrent)
        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertEquals("/api/v1/risk/assessment", request.path)
        assertEquals("Bearer test-token", request.getHeader("Authorization"))
        val body = request.body.readUtf8()
        assertTrue(body.contains("\"questionnaire_version\":\"v2\""))
        assertTrue(body.contains("\"question_id\":\"q1\""))
        assertTrue(body.contains("\"option_id\":\"a1\""))
        assertFalse(body.contains("score"))
        assertFalse(body.contains("user_id"))
    }
    @Test fun staleAssessmentIsNotConvertedIntoAResult() = runTest {
        server.enqueue(MockResponse().setResponseCode(409))
        try { repository.assess("v1", mapOf("q1" to "a1")); fail("Stale version must propagate") }
        catch (error: HttpException) { assertEquals(409, error.code()) }
    }
    @Test fun persistedProfileRetainsVersionAndCurrentFlag() = runTest {
        server.enqueue(response(resultJson.replace("\"is_current\":true", "\"is_current\":false")))
        val result = repository.load()!!
        assertEquals("v2", result.version)
        assertEquals("2026-10-04T10:00:00Z", result.calculatedAt)
        assertFalse(result.isCurrent)
        assertEquals("/api/v1/risk/profile", server.takeRequest().path)
    }
}
