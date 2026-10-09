package app.yudy.ui.assets

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.yudy.domain.assets.*
import app.yudy.domain.auth.SessionExpiredException
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import java.util.UUID
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import retrofit2.HttpException

data class BuyUiState(val tokenId: String? = null, val link: BuyLink? = null, val busy: Boolean = false,
    val confirmed: Boolean = false, val launchUrl: String? = null, val error: String? = null,
    val consentRequired: Boolean = false, val sessionExpired: Boolean = false)
@HiltViewModel
class BuyViewModel @Inject constructor(private val repository: BuyRepository): ViewModel() {
    private val mutable = MutableStateFlow(BuyUiState())
    val state = mutable.asStateFlow()
    private var key: Pair<String, String>? = null
    private var job: Job? = null
    private var eventId: String? = null
    fun bind(user: String, id: String) { if(key != (user to id)) { clear(); key = user to id } }
    fun clear() { dismiss(); key = null }
    fun dismiss() { job?.cancel(); eventId = null; mutable.value = BuyUiState() }
    fun preview(tokenId: String) {
        val id = key?.second ?: return
        dismiss(); mutable.value = BuyUiState(tokenId = tokenId, busy = true)
        job = viewModelScope.launch {
            try { mutable.value = state.value.copy(link = repository.preview(id, tokenId), busy = false) }
            catch(error: Exception) { fail(error) }
        }
    }
    fun confirm() {
        val id = key?.second ?: return
        val current = state.value
        val token = current.tokenId ?: return
        if(current.busy || current.link == null) return
        if(current.confirmed) { mutable.value = current.copy(launchUrl = current.link.url, error = null); return }
        val event = eventId ?: UUID.randomUUID().toString().also { eventId = it }
        mutable.value = current.copy(busy = true, error = null)
        job = viewModelScope.launch {
            try {
                val link = repository.confirm(id, token, event)
                mutable.value = state.value.copy(link = link, confirmed = true, launchUrl = link.url, busy = false)
            } catch(error: Exception) { fail(error) }
        }
    }
    fun consumeLaunch() { mutable.value = state.value.copy(launchUrl = null) }
    fun launchFailed() { mutable.value = state.value.copy(error = "Could not open a browser. Try again or return to the asset.") }
    private fun fail(error: Exception) {
        if(error is CancellationException) throw error
        mutable.value = state.value.copy(busy = false, error = if(error is HttpException && error.code() == 404)
            "This tokenized representation is unavailable." else "Could not prepare the external transition. Please retry.",
            consentRequired = error is HttpException && error.code() == 403,
            sessionExpired = error is SessionExpiredException)
    }
}
