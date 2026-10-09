package app.yudy

import app.yudy.data.auth.*
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

private class MemorySessionStore : SessionStore {
    var tokens: TokensDto? = null
    var email: String? = null
    override suspend fun read() = tokens
    override suspend fun readEmail() = email
    override suspend fun write(tokens: TokensDto) { this.tokens = tokens; email = tokens.user.email }
    override suspend fun clear() { tokens = null }
    override suspend fun clearEmail() { email = null }
}

class RemoteAuthRepositoryTest {
    private val server = MockWebServer()
    private val store = MemorySessionStore()
    private lateinit var repository: RemoteAuthRepository
    private val userJson = """{"id":"user-1","email":"test@example.com"}"""
    private val tokensJson = """{"data":{"access_token":"new-access","refresh_token":"new-refresh","user":$userJson}}"""

    @Before fun setup() {
        server.start()
        val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
        val api = Retrofit.Builder().baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(moshi)).build()
            .create(AuthApi::class.java)
        repository = RemoteAuthRepository(api, store)
    }

    @After fun cleanup() { server.shutdown() }

    private fun savedSession() = TokensDto("old-access", "old-refresh", UserDto("user-1", "test@example.com"))
    private fun response(body: String) = MockResponse().setHeader("Content-Type", "application/json").setBody(body)

    @Test fun registerPersistsSessionAndTrimsEmail() = runTest {
        server.enqueue(response(tokensJson))
        val user = repository.register(" test@example.com ", "long-password")
        assertEquals("test@example.com", user.email)
        assertEquals("new-refresh", store.tokens!!.refreshToken)
        assertEquals("test@example.com", repository.rememberedEmail())
        val request = server.takeRequest()
        assertEquals("/api/v1/auth/register", request.path)
        assertTrue(request.body.readUtf8().contains("\"email\":\"test@example.com\""))
    }

    @Test fun restoreValidSessionUsesBearerWithoutRefreshing() = runTest {
        store.tokens = savedSession()
        server.enqueue(response("""{"data":$userJson}"""))
        assertEquals("user-1", repository.restore()!!.id)
        assertEquals("Bearer old-access", server.takeRequest().getHeader("Authorization"))
        assertEquals(1, server.requestCount)
    }

    @Test fun expiredAccessRotatesAndPersistsTokens() = runTest {
        store.tokens = savedSession()
        server.enqueue(MockResponse().setResponseCode(401))
        server.enqueue(response(tokensJson))
        assertEquals("user-1", repository.restore()!!.id)
        assertEquals("new-access", store.tokens!!.accessToken)
        server.takeRequest()
        val refresh = server.takeRequest()
        assertEquals("/api/v1/auth/refresh", refresh.path)
        assertTrue(refresh.body.readUtf8().contains("old-refresh"))
    }

    @Test fun revokedSessionClearsLocalCredentials() = runTest {
        store.tokens = savedSession()
        server.enqueue(MockResponse().setResponseCode(401))
        server.enqueue(MockResponse().setResponseCode(401))
        assertNull(repository.restore())
        assertNull(store.tokens)
    }

    @Test fun serverFailurePreservesSessionForRetry() = runTest {
        store.tokens = savedSession()
        server.enqueue(MockResponse().setResponseCode(503))
        try {
            repository.restore()
            fail("Expected a server error")
        } catch (error: HttpException) {
            assertEquals(503, error.code())
        }
        assertEquals("old-refresh", store.tokens!!.refreshToken)
    }

    @Test fun logoutRevokesBeforeClearingLocalSession() = runTest {
        store.tokens = savedSession()
        store.email = "test@example.com"
        server.enqueue(MockResponse().setResponseCode(204))
        repository.logout()
        assertNull(store.tokens)
        assertEquals("test@example.com", repository.rememberedEmail())
        val request = server.takeRequest()
        assertEquals("/api/v1/auth/logout", request.path)
        assertTrue(request.body.readUtf8().contains("old-refresh"))
    }

    @Test fun deleteAccountUsesBearerAndClearsLocalSession() = runTest {
        store.tokens = savedSession()
        store.email = "test@example.com"
        server.enqueue(MockResponse().setResponseCode(204))
        repository.deleteAccount()
        assertNull(store.tokens)
        assertNull(repository.rememberedEmail())
        val request = server.takeRequest()
        assertEquals("DELETE", request.method)
        assertEquals("/api/v1/users/me", request.path)
        assertEquals("Bearer old-access", request.getHeader("Authorization"))
    }

    @Test fun authorizedRequestRefreshesExpiredAccessAndRetriesOnce() = runTest {
        store.tokens = savedSession()
        server.enqueue(response(tokensJson))
        var attempts = 0
        val result = repository.withAccessToken { token ->
            attempts++
            if (attempts == 1) throw HttpException(retrofit2.Response.error<String>(401,
                "".toResponseBody()))
            token
        }
        assertEquals("new-access", result)
        assertEquals(2, attempts)
        assertEquals("new-refresh", store.tokens!!.refreshToken)
        assertEquals("/api/v1/auth/refresh", server.takeRequest().path)
    }
}
