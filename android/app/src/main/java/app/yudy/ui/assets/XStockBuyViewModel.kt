package app.yudy.ui.assets

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.yudy.domain.assets.SelectionRepository
import app.yudy.domain.assets.XStockVenue
import app.yudy.domain.auth.SessionExpiredException
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class XStockBuyUiState(
    val venues: List<XStockVenue> = emptyList(),
    val busy: Boolean = true,
    val opening: String? = null,
    val error: String? = null,
    val consentRequired: Boolean = false,
    val sessionExpired: Boolean = false,
)

@HiltViewModel
class XStockBuyViewModel @Inject constructor(
    private val repository: SelectionRepository,
) : ViewModel() {
    private val mutable = MutableStateFlow(XStockBuyUiState())
    val state = mutable.asStateFlow()
    private var assetId: String? = null
    private var job: Job? = null

    fun bind(id: String) {
        if (assetId == id) return
        assetId = id
        reload()
    }

    fun reload() {
        val id = assetId ?: return
        job?.cancel()
        mutable.value = XStockBuyUiState()
        job = viewModelScope.launch {
            try { mutable.value = XStockBuyUiState(venues = repository.venues(id), busy = false) }
            catch (error: Exception) { fail(error, "Could not load trading venues. Please retry.") }
        }
    }

    fun recordOpen(venue: XStockVenue, open: () -> Unit) {
        val id = assetId ?: return
        if (state.value.opening != null) return
        mutable.value = state.value.copy(opening = venue.name, error = null)
        open()
        viewModelScope.launch {
            try {
                repository.recordBuy(id, venue.name)
                mutable.value = state.value.copy(opening = null)
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                mutable.value = state.value.copy(opening = null)
            }
        }
    }

    private fun fail(error: Exception, message: String) {
        if (error is CancellationException) throw error
        mutable.value = state.value.copy(busy = false, opening = null, error = message,
            consentRequired = error is HttpException && error.code() == 403,
            sessionExpired = error is SessionExpiredException)
    }
}
