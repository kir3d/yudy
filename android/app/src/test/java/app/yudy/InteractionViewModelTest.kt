package app.yudy

import app.yudy.domain.assets.*
import app.yudy.domain.auth.SessionExpiredException
import app.yudy.ui.assets.*
import java.io.IOException
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.*
import org.junit.Assert.*
import okhttp3.ResponseBody.Companion.toResponseBody
import retrofit2.HttpException
import retrofit2.Response

class FakeInteractionRepository: InteractionRepository {
    var current = InteractionState()
    var failure: Exception? = null
    var pending: CompletableDeferred<InteractionState>? = null
    var views = 0
    var calls = 0
    var assets = listOf(demoAsset("one"))
    override suspend fun state(id: String): InteractionState { failure?.let { throw it }; return current }
    override suspend fun change(id: String, action: String, active: Boolean): InteractionState {
        if (action == "view") { views++; return current }
        calls++; failure?.let { throw it }
        pending?.let { current = it.await(); return current }
        current = when(action) {
            "like" -> current.copy(liked = active, disliked = if(active) false else current.disliked)
            "dislike" -> current.copy(disliked = active, liked = if(active) false else current.liked)
            else -> current.copy(saved = active)
        }
        return current
    }
    override suspend fun saved(): List<AssetSummary> { failure?.let { throw it }; return if(current.saved) assets else emptyList() }
}
@OptIn(ExperimentalCoroutinesApi::class)
class InteractionViewModelTest {
    @Before fun setup() { Dispatchers.setMain(UnconfinedTestDispatcher()) }
    @After fun cleanup() { Dispatchers.resetMain() }
    @Test fun likeDoesNotSaveAndDislikeReplacesLike() {
        val repo = FakeInteractionRepository(); val model = InteractionViewModel(repo)
        model.bind("user", "one"); model.change("like")
        assertEquals(InteractionState(liked = true), model.state.value.value)
        model.change("save"); model.change("dislike")
        assertEquals(InteractionState(disliked = true, saved = true), model.state.value.value)
        model.change("dislike"); model.change("save")
        assertEquals(InteractionState(), model.state.value.value)
    }
    @Test fun waitsForConfirmationAndRejectsDuplicateTap() {
        val repo = FakeInteractionRepository().apply { pending = CompletableDeferred() }
        val model = InteractionViewModel(repo); model.bind("u", "one"); model.change("save")
        assertTrue(model.state.value.busy); assertFalse(model.state.value.value!!.saved)
        model.change("save"); assertEquals(1, repo.calls)
        repo.pending!!.complete(InteractionState(saved = true))
        assertTrue(model.state.value.value!!.saved); assertFalse(model.state.value.busy)
    }
    @Test fun ambiguousFailureRequiresSynchronizationBeforeAnotherMutation() {
        val repo = FakeInteractionRepository(); val model = InteractionViewModel(repo)
        model.bind("u", "one"); repo.failure = IOException(); model.change("save")
        assertFalse(model.state.value.value!!.saved); assertNotNull(model.state.value.error)
        repo.failure = null; repo.current = InteractionState(saved = true)
        model.change("save"); assertEquals(1, repo.calls)
        model.reload(); assertTrue(model.state.value.value!!.saved)
        model.change("save"); assertFalse(model.state.value.value!!.saved)
    }
    @Test fun viewOncePerOpenNeverOverwritesActionState() {
        val repo = FakeInteractionRepository(); val model = InteractionViewModel(repo)
        model.bind("u", "one"); model.recordView(); model.recordView(); model.change("like")
        assertEquals(1, repo.views); assertTrue(model.state.value.value!!.liked)
        model.clear(); model.bind("u", "one"); model.recordView(); assertEquals(2, repo.views)
    }
    @Test fun userChangeCancelsOldWriteAndClearsPreviousState() {
        val repo = FakeInteractionRepository().apply { pending = CompletableDeferred() }
        val model = InteractionViewModel(repo); model.bind("first", "one"); model.change("save")
        model.bind("second", "one"); repo.pending!!.complete(InteractionState(saved = true))
        assertFalse(model.state.value.value!!.saved)
    }
    @Test fun authorizationFailureExposesGuards() {
        val repo = FakeInteractionRepository().apply { failure = HttpException(Response.error<Any>(403, "{}".toResponseBody())) }
        val model = InteractionViewModel(repo); model.bind("u", "one")
        assertTrue(model.state.value.consentRequired)
        repo.failure = SessionExpiredException(); model.reload(); assertTrue(model.state.value.sessionExpired)
    }
    @Test fun savedHasExplicitEmptyFailureRetryAndClearsOnUserChange() {
        val repo = FakeSelectionRepository(); val model = SavedViewModel(repo)
        model.bind("first"); assertTrue(model.state.value.items.isEmpty())
        repo.savedItems = listOf(xstock().copy(interaction = InteractionState(saved = true)))
        model.reload(); assertEquals(1, model.state.value.items.size)
        repo.failure = IOException(); model.reload(); assertNotNull(model.state.value.error); assertTrue(model.state.value.items.isEmpty())
        repo.failure = null; repo.savedItems = emptyList(); model.bind("second")
        assertNull(model.state.value.error); assertTrue(model.state.value.items.isEmpty())
    }
}
