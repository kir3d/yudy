package app.yudy.ui.risk

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.yudy.domain.auth.SessionExpiredException
import app.yudy.domain.risk.*
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class RiskUiState(
    val questionnaire: RiskQuestionnaire? = null,
    val result: RiskResult? = null,
    val answers: Map<String, String> = emptyMap(),
    val step: Int = 0,
    val busy: Boolean = true,
    val editing: Boolean = true,
    val showResult: Boolean = false,
    val reloadRequired: Boolean = false,
    val error: String? = null,
    val consentRequired: Boolean = false,
    val sessionExpired: Boolean = false,
) {
    val question: RiskQuestion? get() = questionnaire?.questions?.getOrNull(step)
    val canContinue: Boolean get() = !busy && !reloadRequired && question?.let { q ->
        q.options.any { it.id == answers[q.id] }
    } == true
    val canSubmit: Boolean get() = canContinue && questionnaire?.questions?.let { questions ->
        questions.isNotEmpty() && questions.all { q -> q.options.any { it.id == answers[q.id] } }
    } == true
    val canCancel: Boolean get() = !busy && !reloadRequired && result?.isCurrent == true && result.version == questionnaire?.version
}

@HiltViewModel
class RiskViewModel @Inject constructor(private val repository: RiskRepository) : ViewModel() {
    private val mutableState = MutableStateFlow(RiskUiState())
    val state = mutableState.asStateFlow()
    private var userId: String? = null
    private var job: Job? = null
    fun bindUser(id: String) {
        if (id == userId) return
        clear(); userId = id; reload()
    }
    fun clear() {
        job?.cancel(); userId = null; mutableState.value = RiskUiState()
    }
    fun reload() {
        if (userId == null || job?.isActive == true) return
        execute {
            val questionnaire = repository.questions()
            val result = repository.load()
            mutableState.value = RiskUiState(questionnaire = questionnaire, result = result, busy = false,
                editing = result == null || !result.isCurrent || result.version != questionnaire.version)
        }
    }
    fun select(optionId: String) {
        val current = state.value
        val question = current.question ?: return
        if (current.busy || current.reloadRequired || question.options.none { it.id == optionId }) return
        mutableState.value = current.copy(answers = current.answers + (question.id to optionId), error = null)
    }
    fun next() {
        val current = state.value
        if (current.canContinue && current.step < (current.questionnaire?.questions?.lastIndex ?: 0))
            mutableState.value = current.copy(step = current.step + 1)
    }
    fun back() {
        if (!state.value.busy && state.value.step > 0) mutableState.value = state.value.copy(step = state.value.step - 1)
    }
    fun submit() {
        val current = state.value
        if (!current.editing || !current.canSubmit || current.step != current.questionnaire!!.questions.lastIndex) return
        execute {
            val result = repository.assess(current.questionnaire.version, current.answers)
            mutableState.value = state.value.copy(result = result, busy = false, editing = false, showResult = true)
        }
    }
    fun continueToProfile() {
        if (!state.value.busy && state.value.result != null) mutableState.value = state.value.copy(showResult = false)
    }
    fun retake() {
        if (state.value.busy || userId == null) return
        execute {
            val questionnaire = repository.questions()
            mutableState.value = state.value.copy(questionnaire = questionnaire, answers = emptyMap(),
                step = 0, busy = false, editing = true, showResult = false, reloadRequired = false)
        }
    }
    fun cancel() {
        if (state.value.canCancel) mutableState.value = state.value.copy(editing = false, showResult = false, error = null)
    }
    private fun execute(action: suspend () -> Unit) {
        mutableState.value = state.value.copy(busy = true, error = null, consentRequired = false, sessionExpired = false)
        job = viewModelScope.launch {
            try { action() }
            catch (error: CancellationException) { throw error }
            catch (error: Exception) {
                val stale = error is HttpException && error.code() == 409
                val consent = error is HttpException && error.code() == 403
                val expired = error is SessionExpiredException
                mutableState.value = state.value.copy(busy = false, reloadRequired = stale || state.value.reloadRequired,
                    consentRequired = consent, sessionExpired = expired, error = when {
                        stale -> "The questionnaire was updated. Reload and answer the current version."
                        consent -> "Please review the current legal documents."
                        expired -> "Your session has expired. Please sign in again."
                        else -> "Couldn’t load or save your assessment. Your result has not been confirmed. Please retry."
                    })
            }
        }
    }
}
