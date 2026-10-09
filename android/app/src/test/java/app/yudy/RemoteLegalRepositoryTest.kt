package app.yudy

import app.yudy.data.auth.SessionAuthorizer
import app.yudy.data.legal.LegalApi
import app.yudy.data.legal.RemoteLegalRepository
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

class RemoteLegalRepositoryTest {
    private val server = MockWebServer()
    private lateinit var repository: RemoteLegalRepository
    private val stateJson = """{"data":{"documents":[{"id":"doc-1","type":"TERMS_OF_USE","version":"demo-v2","title":"Terms","content":"Full text","is_mandatory":true,"accepted":false,"accepted_at":null}],"all_required_accepted":false}}"""

    @Before fun setup() {
        server.start()
        val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
        val api = Retrofit.Builder().baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(moshi)).build().create(LegalApi::class.java)
        repository = RemoteLegalRepository(api, object : SessionAuthorizer {
            override suspend fun <T> withAccessToken(request: suspend (String) -> T) = request("test-token")
        })
    }
    @After fun cleanup() { server.shutdown() }
    private fun response() = MockResponse().setHeader("Content-Type", "application/json").setBody(stateJson)

    @Test fun loadMapsDocumentVersionsContentAndConsentState() = runTest {
        server.enqueue(response())
        val snapshot = repository.load()
        assertFalse(snapshot.allRequiredAccepted)
        assertEquals("Full text", snapshot.documents.single().content)
        assertEquals("demo-v2", snapshot.documents.single().version)
        assertNull(snapshot.documents.single().acceptedAt)
        val request = server.takeRequest()
        assertEquals("/api/v1/legal/consents/me", request.path)
        assertEquals("Bearer test-token", request.getHeader("Authorization"))
    }

    @Test fun submitSendsOnlyExplicitVersionedAcceptanceAndTrustsServerState() = runTest {
        server.enqueue(response())
        val docs = repository.load().documents
        server.takeRequest()
        server.enqueue(response())
        val result = repository.accept(docs)
        assertFalse(result.allRequiredAccepted)
        val request = server.takeRequest()
        assertEquals("/api/v1/legal/consents", request.path)
        val body = request.body.readUtf8()
        assertTrue(body.contains("\"document_id\":\"doc-1\""))
        assertTrue(body.contains("\"version\":\"demo-v2\""))
        assertTrue(body.contains("\"accepted\":true"))
        assertFalse(body.contains("user_id"))
    }
}
