package app.yudy

import app.yudy.domain.learn.*
import app.yudy.ui.learn.LearnViewModel
import java.io.IOException
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.*
import org.junit.Assert.*
import okhttp3.ResponseBody.Companion.toResponseBody
import retrofit2.HttpException
import retrofit2.Response

class FakeLearnRepository: LearnRepository {
    var failure: Exception? = null
    var pending: CompletableDeferred<LearnArticle>? = null
    val example = LearnArticle("one", "topic", "Topic", "Summary", "2026-10-04", "Paragraph one\n\nParagraph two")
    override suspend fun articles(): List<LearnArticle> { failure?.let { throw it }; return listOf(example.copy(content = null)) }
    override suspend fun article(slug: String): LearnArticle { failure?.let { throw it }; return pending?.await() ?: example.copy(slug = slug) }
}
@OptIn(ExperimentalCoroutinesApi::class)
class LearnViewModelTest {
    @Before fun setup() { Dispatchers.setMain(UnconfinedTestDispatcher()) }
    @After fun cleanup() { Dispatchers.resetMain() }
    @Test fun listAndArticleLoadSeparatelyAndBackPreservesList() {
        val model = LearnViewModel(FakeLearnRepository()); model.reload()
        assertNull(model.state.value.articles.single().content)
        model.open("topic"); assertNotNull(model.state.value.article!!.content)
        model.closeArticle(); assertNull(model.state.value.article); assertNull(model.state.value.slug)
        assertEquals(1, model.state.value.articles.size)
    }
    @Test fun failureAndRetryNeverShowOldArticleContent() {
        val repo = FakeLearnRepository(); val model = LearnViewModel(repo); model.reload(); model.open("topic")
        repo.failure = IOException(); model.open("other")
        assertNull(model.state.value.article); assertNotNull(model.state.value.articleError)
        repo.failure = null; model.open("other"); assertEquals("other", model.state.value.article!!.slug)
    }
    @Test fun listFailureIsExplicitAndRetryRecovers() {
        val repo = FakeLearnRepository().apply { failure = IOException() }; val model = LearnViewModel(repo)
        model.reload(); assertNotNull(model.state.value.error); assertFalse(model.state.value.busy)
        repo.failure = null; model.reload(); assertNull(model.state.value.error); assertEquals(1, model.state.value.articles.size)
    }
    @Test fun backCancelsPendingArticleResponse() {
        val repo = FakeLearnRepository().apply { pending = CompletableDeferred() }; val model = LearnViewModel(repo)
        model.reload(); model.open("topic"); model.closeArticle(); repo.pending!!.complete(repo.example)
        assertNull(model.state.value.slug); assertNull(model.state.value.article)
        model.clear(); assertTrue(model.state.value.articles.isEmpty())
    }
    @Test fun missingArticleIsNotAnEmptySuccess() {
        val repo = FakeLearnRepository().apply { failure = HttpException(Response.error<Any>(404, "{}".toResponseBody())) }
        val model = LearnViewModel(repo); model.open("missing")
        assertTrue(model.state.value.articleError!!.contains("unavailable")); assertNull(model.state.value.article)
    }
}
