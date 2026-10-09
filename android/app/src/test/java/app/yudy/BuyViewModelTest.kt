package app.yudy

import app.yudy.domain.assets.*
import app.yudy.domain.auth.SessionExpiredException
import app.yudy.ui.assets.BuyViewModel
import java.io.IOException
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.*
import org.junit.Assert.*
import okhttp3.ResponseBody.Companion.toResponseBody
import retrofit2.HttpException
import retrofit2.Response

class FakeBuyRepository: BuyRepository {
    var failure: Exception? = null
    var pending: CompletableDeferred<BuyLink>? = null
    var ids = mutableListOf<String>()
    val link = BuyLink("Demo", "https://example.test/assets/TOKEN", "token", "TOKEN", true)
    override suspend fun preview(assetId: String, tokenId: String): BuyLink { failure?.let { throw it }; return link.copy(tokenId = tokenId) }
    override suspend fun confirm(assetId: String, tokenId: String, eventId: String): BuyLink {
        ids.add(eventId); failure?.let { throw it }; return pending?.await() ?: link.copy(tokenId = tokenId)
    }
}
@OptIn(ExperimentalCoroutinesApi::class)
class BuyViewModelTest {
    @Before fun setup() { Dispatchers.setMain(UnconfinedTestDispatcher()) }
    @After fun cleanup() { Dispatchers.resetMain() }
    @Test fun previewAndCancelNeverConfirmOrLaunch() {
        val repo = FakeBuyRepository(); val model = BuyViewModel(repo); model.bind("u", "asset"); model.preview("token")
        assertNotNull(model.state.value.link); assertNull(model.state.value.launchUrl); assertTrue(repo.ids.isEmpty())
        model.dismiss(); assertNull(model.state.value.tokenId); assertTrue(repo.ids.isEmpty())
    }
    @Test fun duplicateTapBlockedAndConfirmedLinkConsumedOnce() {
        val repo = FakeBuyRepository().apply { pending = CompletableDeferred() }; val model = BuyViewModel(repo)
        model.bind("u", "asset"); model.preview("token"); model.confirm(); model.confirm()
        assertEquals(1, repo.ids.size); assertNull(model.state.value.launchUrl)
        repo.pending!!.complete(repo.link); assertEquals(repo.link.url, model.state.value.launchUrl)
        model.consumeLaunch(); assertNull(model.state.value.launchUrl); assertTrue(model.state.value.confirmed)
        model.launchFailed(); model.confirm()
        assertEquals(1, repo.ids.size); assertEquals(repo.link.url, model.state.value.launchUrl)
    }
    @Test fun ambiguousConfirmationRetryReusesEventId() {
        val repo = FakeBuyRepository(); val model = BuyViewModel(repo); model.bind("u", "asset"); model.preview("token")
        repo.failure = IOException(); model.confirm(); assertNull(model.state.value.launchUrl); assertNotNull(model.state.value.error)
        repo.failure = null; model.confirm()
        assertEquals(2, repo.ids.size); assertEquals(repo.ids[0], repo.ids[1]); assertTrue(model.state.value.confirmed)
    }
    @Test fun accountChangeCancelsPendingLaunch() {
        val repo = FakeBuyRepository().apply { pending = CompletableDeferred() }; val model = BuyViewModel(repo)
        model.bind("first", "asset"); model.preview("token"); model.confirm(); model.bind("second", "asset")
        repo.pending!!.complete(repo.link); assertNull(model.state.value.launchUrl); assertNull(model.state.value.link)
    }
    @Test fun legalAndSessionErrorsExposeGuards() {
        val repo = FakeBuyRepository().apply { failure = HttpException(Response.error<Any>(403, "{}".toResponseBody())) }
        val model = BuyViewModel(repo); model.bind("u", "asset"); model.preview("token"); assertTrue(model.state.value.consentRequired)
        repo.failure = SessionExpiredException(); model.preview("token"); assertTrue(model.state.value.sessionExpired)
    }
    @Test fun externalUrlsRejectCredentialsUnsafeSchemesAndReleaseHttp() {
        assertTrue(validExternalBuyUrl("https://example.test/assets/TOKEN", false))
        assertTrue(validExternalBuyUrl("http://localhost:8001/assets/TOKEN", true))
        for(url in listOf("http://localhost:8001", "javascript:alert(1)", "file:///tmp/page", "https://user:pass@example.test", "https://example.test/#fragment", "https://example.test:99999", "https://example.test/white space"))
            assertFalse(url, validExternalBuyUrl(url, false))
    }
}
