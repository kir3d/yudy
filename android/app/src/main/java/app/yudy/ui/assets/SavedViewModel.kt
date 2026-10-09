package app.yudy.ui.assets

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.yudy.domain.assets.*
import app.yudy.domain.auth.SessionExpiredException
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class SavedUiState(val items: List<XStockSuggestion> = emptyList(), val busy: Boolean = true,
    val error: String? = null, val actionError: String? = null, val changing: Set<String> = emptySet(),
    val consentRequired: Boolean = false, val sessionExpired: Boolean = false)
@HiltViewModel
class SavedViewModel @Inject constructor(private val repository: SelectionRepository): ViewModel() {
    private val mutable = MutableStateFlow(SavedUiState())
    val state = mutable.asStateFlow()
    private var user: String? = null
    private var job: Job? = null
    fun bind(id: String) {
        if (user != id) { clear(); user = id }
        reload()
    }
    fun clear() { job?.cancel(); user = null; mutable.value = SavedUiState() }
    fun reload() {
        if (user == null) return
        job?.cancel(); mutable.value = SavedUiState()
        job = viewModelScope.launch {
            try { mutable.value = SavedUiState(repository.savedXstocks(), busy = false) }
            catch (error: Exception) {
                if (error is CancellationException) throw error
                mutable.value = SavedUiState(busy = false, error = "Could not load Saved. Please retry.",
                    consentRequired = error is HttpException && error.code() == 403,
                    sessionExpired = error is SessionExpiredException)
            }
        }
    }
    fun change(item: XStockSuggestion, action: String) {
        if (item.id in state.value.changing) return
        val active = when (action) {
            "like" -> !item.interaction.liked
            "dislike" -> !item.interaction.disliked
            "save" -> !item.interaction.saved
            else -> return
        }
        mutable.value = state.value.copy(changing = state.value.changing + item.id, actionError = null)
        viewModelScope.launch {
            try {
                val updated = repository.changeXstock(item.id, action, active)
                mutable.value = state.value.copy(
                    items = if (!updated.saved) state.value.items.filterNot { it.id == item.id }
                    else state.value.items.map { if (it.id == item.id) it.copy(interaction = updated) else it },
                    changing = state.value.changing - item.id,
                )
            } catch (error: CancellationException) { throw error }
            catch (error: Exception) {
                mutable.value = state.value.copy(changing = state.value.changing - item.id,
                    actionError = "Could not update this action. Please try again.",
                    consentRequired = error is HttpException && error.code() == 403,
                    sessionExpired = error is SessionExpiredException)
            }
        }
    }
}
