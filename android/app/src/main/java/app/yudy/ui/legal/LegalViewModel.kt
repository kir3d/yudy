package app.yudy.ui.legal

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.yudy.domain.auth.SessionExpiredException
import app.yudy.domain.legal.ConsentSnapshot
import app.yudy.domain.legal.LegalDocument
import app.yudy.domain.legal.LegalRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import java.io.IOException
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class LegalUiState(
    val documents: List<LegalDocument> = emptyList(),
    val busy: Boolean = true,
    val complete: Boolean = false,
    val error: String? = null,
    val sessionExpired: Boolean = false,
    val openedType: String? = null,
) {
    private val requiredTypes get() = setOf("TERMS_OF_USE", "PRIVACY_POLICY", "PERSONAL_DATA_CONSENT")
    val openedDocument: LegalDocument? get() = documents.firstOrNull { it.type == openedType }
    val canAccept: Boolean get() = !busy && !complete &&
        documents.filter { it.mandatory }.map { it.type }.toSet() == requiredTypes &&
        documents.any { it.mandatory && !it.accepted }
}

@HiltViewModel
class LegalViewModel @Inject constructor(private val repository: LegalRepository) : ViewModel() {
    private val mutableState = MutableStateFlow(LegalUiState())
    val state = mutableState.asStateFlow()
    private var userId: String? = null
    private var job: Job? = null

    fun bindUser(id: String) {
        if (id == userId) return
        clear()
        userId = id
        reload()
    }

    fun clear() {
        job?.cancel()
        userId = null
        mutableState.value = LegalUiState()
    }

    fun reload() {
        if (userId == null || job?.isActive == true) return
        execute { repository.load() }
    }

    fun accept() {
        if (!state.value.canAccept) return
        val selected = state.value.documents.filter { it.mandatory && !it.accepted }
        execute { repository.accept(selected) }
    }

    fun openDocument(type: String) {
        if (state.value.documents.any { it.type == type }) {
            mutableState.value = state.value.copy(openedType = type)
        }
    }

    fun closeDocument() {
        mutableState.value = state.value.copy(openedType = null)
    }

    private fun execute(action: suspend () -> ConsentSnapshot) {
        mutableState.value = state.value.copy(busy = true, error = null, complete = false)
        job = viewModelScope.launch {
            try {
                val snapshot = action()
                mutableState.value = LegalUiState(documents = snapshot.documents, busy = false,
                    complete = snapshot.allRequiredAccepted)
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                val message = when {
                    error is SessionExpiredException -> "Your session has expired. Please sign in again."
                    error is HttpException && error.code() == 409 -> "Documents were updated. Reload and review their current versions."
                    error is IOException -> "Couldn’t connect. Your acceptance has not been confirmed. Please retry."
                    else -> "Couldn’t load or save your consent. Please retry."
                }
                mutableState.value = state.value.copy(busy = false, error = message,
                    sessionExpired = error is SessionExpiredException)
            }
        }
    }
}
