package app.yudy.ui.assets

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.yudy.domain.assets.*
import app.yudy.domain.auth.SessionExpiredException
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import retrofit2.HttpException

data class ForYouUiState(val items: List<XStockSuggestion> = emptyList(), val source: String? = null,
    val generatedAt: String? = null, val sentToAi: List<String> = emptyList(),
    val neverSent: List<String> = emptyList(), val busy: Boolean = true,
    val error: String? = null, val actionError: String? = null, val changing: Set<String> = emptySet(),
    val profileRequired: Boolean = false, val consentRequired: Boolean = false, val sessionExpired: Boolean = false)
@HiltViewModel
class ForYouViewModel @Inject constructor(private val repository: SelectionRepository): ViewModel() {
    private val mutable = MutableStateFlow(ForYouUiState())
    val state = mutable.asStateFlow()
    private var user: String? = null
    private var job: Job? = null
    private val actionJobs = mutableMapOf<String, Job>()
    fun bind(id: String) {
        if (user != id) { clear(); user = id }
        reload()
    }
    fun clear() { job?.cancel(); actionJobs.values.forEach(Job::cancel); actionJobs.clear(); user = null; mutable.value = ForYouUiState() }
    fun reload(forceRefresh: Boolean = false) {
        if(user == null) return
        job?.cancel(); mutable.value = ForYouUiState()
        job = viewModelScope.launch {
            try {
                val result = repository.xstocks(forceRefresh)
                mutable.value = ForYouUiState(result.items, result.source, result.generatedAt,
                    result.sentToAi, result.neverSent, busy = false)
            } catch(error: Exception) { fail(error) }
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
        actionJobs[item.id] = viewModelScope.launch {
            try {
                val interaction = repository.changeXstock(item.id, action, active)
                val items = if (action == "dislike" && interaction.disliked) {
                    state.value.items.filterNot { it.id == item.id }
                } else {
                    state.value.items.map { current ->
                        if (current.id == item.id) current.copy(interaction = interaction) else current
                    }
                }
                mutable.value = state.value.copy(items = items,
                    changing = state.value.changing - item.id)
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                mutable.value = state.value.copy(changing = state.value.changing - item.id,
                    actionError = "Could not update this action. Please try again.",
                    consentRequired = error is HttpException && error.code() == 403,
                    sessionExpired = error is SessionExpiredException)
            } finally { actionJobs.remove(item.id) }
        }
    }
    private fun fail(error: Exception) {
        if(error is CancellationException) throw error
        mutable.value = state.value.copy(busy = false,
            error = "Could not prepare your xStocks selection. Please retry.",
            profileRequired = error is HttpException && error.code() == 409,
            consentRequired = error is HttpException && error.code() == 403,
            sessionExpired = error is SessionExpiredException)
    }
}
