package app.yudy.ui.assets

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.yudy.domain.assets.*
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException

val historyPeriods = linkedMapOf("1D" to "1D", "1M" to "1M", "1Y" to "1Y", "3Y" to "3Y", "ALL" to "All time")
data class AssetDetailsUiState(val id: String? = null, val details: AssetDetails? = null,
    val history: PriceHistory? = null, val period: String = "1Y", val busy: Boolean = true,
    val historyBusy: Boolean = false, val error: String? = null, val historyError: String? = null)

@HiltViewModel
class AssetDetailsViewModel @Inject constructor(private val repository: AssetRepository) : ViewModel() {
    private val mutableState = MutableStateFlow(AssetDetailsUiState())
    val state = mutableState.asStateFlow()
    private var job: Job? = null
    private var historyJob: Job? = null
    fun bind(id: String) { if (id != state.value.id) { clear(); mutableState.value = state.value.copy(id = id); reload() } }
    fun clear() { job?.cancel(); historyJob?.cancel(); mutableState.value = AssetDetailsUiState() }
    fun reload() {
        val id = state.value.id ?: return
        job?.cancel(); historyJob?.cancel()
        mutableState.value = AssetDetailsUiState(id = id)
        job = viewModelScope.launch {
            try {
                val detail = repository.details(id)
                mutableState.value = state.value.copy(details = detail, history = detail.history, busy = false)
            } catch (error: CancellationException) { throw error }
            catch (error: Exception) { mutableState.value = state.value.copy(busy = false,
                error = if (error is HttpException && error.code() == 404) "This asset is unavailable. Return to Discover."
                    else "Couldn’t load the asset. Please retry.") }
        }
    }
    fun period(value: String) {
        val current = state.value
        val id = current.id ?: return
        if (current.busy || current.details == null || value !in historyPeriods) return
        historyJob?.cancel()
        mutableState.value = current.copy(period = value, history = null, historyBusy = true, historyError = null)
        historyJob = viewModelScope.launch {
            try {
                val history = repository.history(id, value)
                mutableState.value = state.value.copy(history = history, historyBusy = false)
            } catch (error: CancellationException) { throw error }
            catch (error: Exception) { mutableState.value = state.value.copy(historyBusy = false,
                historyError = "Couldn’t load this period. Please retry.") }
        }
    }
}
