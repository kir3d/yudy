package app.yudy

import app.yudy.domain.assets.*
import app.yudy.domain.auth.SessionExpiredException
import app.yudy.ui.assets.ForYouViewModel
import java.io.IOException
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.*
import org.junit.Assert.*
import retrofit2.HttpException
import retrofit2.Response

fun xstock(symbol: String = "AAPLx") = XStockSuggestion(
    id = symbol,
    symbol = symbol,
    name = "Apple xStock",
    underlyingSymbol = "AAPL",
    assetType = "STOCK",
    currency = "USD",
    price = "250.00",
    asOf = "2026-10-07T00:00:00Z",
    logoUrl = null,
    networks = listOf("Solana", "Ethereum"),
    reason = "Matches your technology interest for exploration.",
)

class FakeSelectionRepository: SelectionRepository {
    var failure: Exception? = null
    var pending: CompletableDeferred<XStockSelection>? = null
    var calls = 0
    var lastForceRefresh = false
    var current = XStockSelection(listOf(xstock()), "official", "2026-10-07T00:00:00Z",
        listOf("risk_category", "interests"), listOf("email", "user_id"))
    override suspend fun feed(cursor: String?) = SelectionPage(emptyList(), 0, null)
    override suspend fun xstocks(forceRefresh: Boolean): XStockSelection {
        calls++
        lastForceRefresh = forceRefresh
        failure?.let { throw it }
        pending?.let { return it.await() }
        return current
    }
    var catalogPage = XStockPage(listOf(xstock()), 1, null)
    var savedItems = emptyList<XStockSuggestion>()
    var lastAction: Triple<String, String, Boolean>? = null
    override suspend fun catalog(search: String?, assetType: String?, sort: String, cursor: String?): XStockPage {
        failure?.let { throw it }
        return catalogPage
    }
    override suspend fun savedXstocks(): List<XStockSuggestion> { failure?.let { throw it }; return savedItems }
    override suspend fun changeXstock(id: String, action: String, active: Boolean): InteractionState {
        failure?.let { throw it }
        lastAction = Triple(id, action, active)
        val item = (current.items + catalogPage.items + savedItems).first { it.id == id }
        return when (action) {
            "like" -> item.interaction.copy(liked = active, disliked = if (active) false else item.interaction.disliked)
            "dislike" -> item.interaction.copy(disliked = active, liked = if (active) false else item.interaction.liked)
            else -> item.interaction.copy(saved = active)
        }
    }
    override suspend fun venues(id: String) = listOf(XStockVenue("Kraken", "CEX", "https://example.test", null))
    override suspend fun recordBuy(id: String, venue: String) = Unit
}

@OptIn(ExperimentalCoroutinesApi::class)
class ForYouViewModelTest {
    @Before fun setup() { Dispatchers.setMain(UnconfinedTestDispatcher()) }
    @After fun cleanup() { Dispatchers.resetMain() }

    @Test fun loadsRealXstocksAndPrivacyMetadata() {
        val repo = FakeSelectionRepository()
        val model = ForYouViewModel(repo)
        model.bind("u")
        assertEquals("AAPLx", model.state.value.items.single().symbol)
        assertEquals(listOf("email", "user_id"), model.state.value.neverSent)
        assertEquals("official", model.state.value.source)
    }

    @Test fun refreshRequestsANewAiSelection() {
        val repo = FakeSelectionRepository()
        val model = ForYouViewModel(repo)
        model.bind("u")
        repo.current = repo.current.copy(items = listOf(xstock("SPYx")))
        model.reload(forceRefresh = true)
        assertEquals(2, repo.calls)
        assertTrue(repo.lastForceRefresh)
        assertEquals("SPYx", model.state.value.items.single().symbol)
    }

    @Test fun loadFailureIsVisibleAndRetryRecovers() {
        val repo = FakeSelectionRepository().apply { failure = IOException() }
        val model = ForYouViewModel(repo)
        model.bind("u")
        assertNotNull(model.state.value.error)
        assertFalse(model.state.value.busy)
        repo.failure = null
        model.reload(forceRefresh = true)
        assertEquals(1, model.state.value.items.size)
    }

    @Test fun accountChangeDiscardsPendingPersonalizedResponse() {
        val repo = FakeSelectionRepository().apply { pending = CompletableDeferred() }
        val model = ForYouViewModel(repo)
        model.bind("first")
        val old = repo.pending!!
        repo.pending = null
        model.bind("second")
        old.complete(XStockSelection(emptyList(), "old", "", emptyList(), emptyList()))
        assertEquals("AAPLx", model.state.value.items.single().symbol)
        model.clear()
        assertTrue(model.state.value.items.isEmpty())
    }

    @Test fun legalProfileAndSessionFailuresExposeGuards() {
        val repo = FakeSelectionRepository().apply {
            failure = HttpException(Response.error<Any>(403, "{}".toResponseBody()))
        }
        val model = ForYouViewModel(repo)
        model.bind("u")
        assertTrue(model.state.value.consentRequired)
        repo.failure = HttpException(Response.error<Any>(409, "{}".toResponseBody()))
        model.reload(forceRefresh = true)
        assertTrue(model.state.value.profileRequired)
        repo.failure = SessionExpiredException()
        model.reload(forceRefresh = true)
        assertTrue(model.state.value.sessionExpired)
    }

    @Test fun dislikeRemovesAssetFromForYouAndSaveKeepsItVisible() {
        val repo = FakeSelectionRepository()
        val model = ForYouViewModel(repo)
        model.bind("u")
        model.change(model.state.value.items.single(), "save")
        assertTrue(model.state.value.items.single().interaction.saved)
        model.change(model.state.value.items.single(), "dislike")
        assertTrue(model.state.value.items.isEmpty())
        assertEquals(Triple("AAPLx", "dislike", true), repo.lastAction)
    }
}
