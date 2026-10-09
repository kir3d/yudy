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

data class InteractionUiState(val value: InteractionState? = null, val busy: Boolean = true,
    val error: String? = null, val consentRequired: Boolean = false, val sessionExpired: Boolean = false)

@HiltViewModel
class InteractionViewModel @Inject constructor(private val repository: InteractionRepository): ViewModel() {
    private val mutable = MutableStateFlow(InteractionUiState())
    val state = mutable.asStateFlow()
    private var key: Pair<String, String>? = null
    private var job: Job? = null
    private var viewJob: Job? = null
    private var viewed = false
    fun bind(user: String, id: String) {
        if (key == (user to id)) return
        clear(); key = user to id; reload()
    }
    fun clear() { job?.cancel(); viewJob?.cancel(); key = null; viewed = false; mutable.value = InteractionUiState() }
    fun reload() {
        val id = key?.second ?: return
        job?.cancel()
        mutable.value = mutable.value.copy(busy = true, error = null, consentRequired = false, sessionExpired = false)
        job = viewModelScope.launch {
            try { mutable.value = InteractionUiState(value = repository.state(id), busy = false) }
            catch (error: Exception) { failure(error, "Could not load your actions. Retry to synchronize.") }
        }
    }
    fun change(action: String) {
        val id = key?.second ?: return
        val current = state.value.value ?: return
        if (state.value.busy || state.value.error != null) return
        val active = when(action) { "like" -> !current.liked; "dislike" -> !current.disliked; "save" -> !current.saved; else -> return }
        mutable.value = state.value.copy(busy = true, error = null)
        job = viewModelScope.launch {
            try { mutable.value = InteractionUiState(repository.change(id, action, active), busy = false) }
            catch (error: Exception) { failure(error, "Action could not be confirmed. Reload your actions before trying again.") }
        }
    }
    fun recordView() {
        val id = key?.second ?: return
        if (viewed) return
        viewed = true
        viewJob = viewModelScope.launch {
            try { repository.change(id, "view", true) }
            catch (error: Exception) {
                if (error is CancellationException) throw error
                // A view signal must never replace a newer button response or block reading.
                if (error is SessionExpiredException || (error is HttpException && error.code() == 403))
                    mutable.value = state.value.copy(consentRequired = error is HttpException, sessionExpired = error is SessionExpiredException)
            }
        }
    }
    private fun failure(error: Exception, message: String) {
        if (error is CancellationException) throw error
        mutable.value = state.value.copy(busy = false, error = message,
            consentRequired = error is HttpException && error.code() == 403,
            sessionExpired = error is SessionExpiredException)
    }
}
