package app.yudy

import app.yudy.domain.assets.*
import app.yudy.ui.assets.DiscoverViewModel
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DiscoverViewModelTest {
    @Before fun setup() { Dispatchers.setMain(UnconfinedTestDispatcher()) }
    @After fun cleanup() { Dispatchers.resetMain() }

    @Test fun loadsLiveCatalogAndKeepsDislikedAssetsVisible() {
        val repository = FakeSelectionRepository().apply {
            catalogPage = XStockPage(listOf(xstock()), 1, null)
        }
        val model = DiscoverViewModel(repository)
        model.bindUser("user")
        val asset = model.state.value.items.single()
        model.change(asset, "dislike")
        assertEquals(1, model.state.value.items.size)
        assertTrue(model.state.value.items.single().interaction.disliked)
    }

    @Test fun searchAndAssetTypeAreSentToCatalog() {
        class CapturingRepository : SelectionRepository by FakeSelectionRepository() {
            var request: List<String?> = emptyList()
            override suspend fun catalog(search: String?, assetType: String?, sort: String, cursor: String?): XStockPage {
                request = listOf(search, assetType, sort, cursor)
                return XStockPage(emptyList(), 0, null)
            }
        }
        val repository = CapturingRepository()
        val model = DiscoverViewModel(repository)
        model.bindUser("user")
        model.searchText("  Apple  ")
        model.apply("STOCK", "name", "Apple")
        assertEquals(listOf("Apple", "STOCK", "name", null), repository.request)
        assertTrue(model.state.value.items.isEmpty())
    }

    @Test fun failedInitialLoadHasRetry() {
        val repository = FakeSelectionRepository().apply { failure = IOException("offline") }
        val model = DiscoverViewModel(repository)
        model.bindUser("user")
        assertNotNull(model.state.value.error)
        repository.failure = null
        model.reload()
        assertNull(model.state.value.error)
        assertEquals(1, model.state.value.items.size)
    }
}
