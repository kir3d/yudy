package app.yudy

import app.yudy.data.learn.*
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.*
import org.junit.*
import org.junit.Assert.*
import retrofit2.*
import retrofit2.converter.moshi.MoshiConverterFactory

class RemoteLearnRepositoryTest {
    private val server = MockWebServer()
    private lateinit var repository: RemoteLearnRepository
    private val summary = """{"id":"one","slug":"topic","title":"Topic","summary":"Summary","updated_at":"2026-10-04T12:00:00Z"}"""
    @Before fun setup() {
        server.start()
        val api = Retrofit.Builder().baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()))
            .build().create(LearnApi::class.java)
        repository = RemoteLearnRepository(api)
    }
    @After fun cleanup() { server.shutdown() }
    @Test fun publicListMapsSummaryAndDetailMapsContent() = runTest {
        server.enqueue(MockResponse().setBody("""{"data":[$summary]}"""))
        assertEquals("Topic", repository.articles().single().title)
        val list = server.takeRequest(); assertEquals("/api/v1/learn/articles", list.path); assertNull(list.getHeader("Authorization"))
        server.enqueue(MockResponse().setBody("""{"data":${summary.dropLast(1)},"content":"Full article"}}"""))
        assertEquals("Full article", repository.article("topic").content)
        assertEquals("/api/v1/learn/articles/topic", server.takeRequest().path)
    }
    @Test fun missingContentAndHttpErrorsPropagate() = runTest {
        server.enqueue(MockResponse().setBody("""{"data":$summary}"""))
        try { repository.article("topic"); fail("Missing content") } catch(expected: IllegalStateException) { }
        server.enqueue(MockResponse().setResponseCode(404))
        try { repository.article("missing"); fail("Missing article") } catch(error: HttpException) { assertEquals(404, error.code()) }
    }
}
