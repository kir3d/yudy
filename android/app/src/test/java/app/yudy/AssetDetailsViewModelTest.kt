package app.yudy

import app.yudy.domain.assets.*
import app.yudy.ui.assets.AssetDetailsViewModel
import java.io.IOException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

@OptIn(ExperimentalCoroutinesApi::class)
class AssetDetailsViewModelTest {
    @Before fun setup() { Dispatchers.setMain(UnconfinedTestDispatcher()) }
    @After fun cleanup() { Dispatchers.resetMain() }
    @Test fun loadsUnderlyingDetailsAndInitialYearHistory() {
        val model = AssetDetailsViewModel(FakeAssetRepository())
        model.bind("one")
        assertEquals("one", model.state.value.details!!.asset.id)
        assertEquals("1Y", model.state.value.history!!.period)
        assertFalse(model.state.value.busy)
        assertNull(model.state.value.details!!.fundamentals)
    }
    @Test fun periodChangeClearsOldChartAndCancelsPreviousPeriodRequest() {
        val repository = FakeAssetRepository().apply { historyPending["1D"] = CompletableDeferred() }
        val model = AssetDetailsViewModel(repository)
        model.bind("one"); model.period("1D")
        assertNull(model.state.value.history)
        assertTrue(model.state.value.historyBusy)
        model.period("3Y")
        repository.historyPending["1D"]!!.complete(demoHistory("1D"))
        assertEquals("3Y", model.state.value.period)
        assertEquals("3Y", model.state.value.history!!.period)
        assertFalse(model.state.value.historyBusy)
    }
    @Test fun failedHistoryKeepsAssetDetailsAndAllowsRetry() {
        val repository = FakeAssetRepository()
        val model = AssetDetailsViewModel(repository)
        model.bind("one")
        repository.historyFailure = IOException("offline"); model.period("ALL")
        assertNotNull(model.state.value.details)
        assertNull(model.state.value.history)
        assertNotNull(model.state.value.historyError)
        repository.historyFailure = null; model.period("ALL")
        assertEquals("ALL", model.state.value.history!!.period)
        assertNull(model.state.value.historyError)
    }
    @Test fun inactiveAssetFailureIsExplicitAndReloadCanRecover() {
        val repository = FakeAssetRepository().apply {
            detailFailure = HttpException(Response.error<Any>(404, "{}".toResponseBody()))
        }
        val model = AssetDetailsViewModel(repository)
        model.bind("one")
        assertTrue(model.state.value.error!!.contains("unavailable"))
        assertNull(model.state.value.details)
        repository.detailFailure = null; model.reload()
        assertEquals("one", model.state.value.details!!.asset.id)
    }
    @Test fun closingAssetDiscardsPendingDetailResponse() {
        val repository = FakeAssetRepository().apply { detailPending = CompletableDeferred() }
        val model = AssetDetailsViewModel(repository)
        model.bind("one"); model.clear()
        repository.detailPending!!.complete(demoDetail("one"))
        assertNull(model.state.value.id)
        assertNull(model.state.value.details)
    }
}
