package app.yudy.ui.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.yudy.domain.auth.SessionExpiredException
import app.yudy.domain.profile.*
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException

val experienceChoices = linkedMapOf("NEW" to "I’m new to investing", "SOME" to "I have some experience",
    "REGULAR" to "I invest regularly", "EXPERIENCED" to "I’m an experienced investor")
val horizonChoices = linkedMapOf("UNDER_ONE" to "Less than 1 year", "ONE_THREE" to "1–3 years",
    "THREE_FIVE" to "3–5 years", "FIVE_PLUS" to "5+ years")

data class ProfileUiState(
    val options: ProfileOptions? = null,
    val profile: InvestorProfile? = null,
    val draft: InvestorProfile = InvestorProfile(),
    val editing: Boolean = true,
    val step: Int = 0,
    val busy: Boolean = true,
    val error: String? = null,
    val consentRequired: Boolean = false,
    val sessionExpired: Boolean = false,
) {
    val canContinue: Boolean get() = !busy && when (step) {
        0 -> draft.experience in experienceChoices
        1 -> draft.goalIds.isNotEmpty()
        2 -> draft.horizon in horizonChoices
        else -> true
    }
}

@HiltViewModel
class ProfileViewModel @Inject constructor(private val repository: ProfileRepository) : ViewModel() {
    private val mutableState = MutableStateFlow(ProfileUiState())
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
        mutableState.value = ProfileUiState()
    }
    fun reload() {
        if (userId == null || job?.isActive == true) return
        execute {
            val options = repository.options()
            val profile = repository.load()
            mutableState.value = ProfileUiState(options = options, profile = profile,
                draft = profile ?: InvestorProfile(), editing = profile == null, busy = false)
        }
    }
    fun experience(code: String) {
        if (state.value.busy || code !in experienceChoices) return
        mutableState.value = state.value.copy(draft = state.value.draft.copy(experience = code))
    }
    fun horizon(code: String) {
        if (state.value.busy || code !in horizonChoices) return
        mutableState.value = state.value.copy(draft = state.value.draft.copy(horizon = code))
    }
    fun toggle(kind: String, id: String) {
        val current = state.value
        if (current.busy) return
        val options = current.options ?: return
        val allowed = when (kind) { "goals" -> options.goals; "regions" -> options.regions; else -> options.interests }
        if (allowed.none { it.id == id }) return
        fun Set<String>.toggled() = if (id in this) this - id else this + id
        val draft = current.draft
        val updated = when (kind) {
            "goals" -> draft.copy(goalIds = draft.goalIds.toggled())
            "regions" -> draft.copy(regionIds = draft.regionIds.toggled())
            "interests" -> draft.copy(interestIds = draft.interestIds.toggled(), excludedInterestIds = draft.excludedInterestIds - id)
            "excluded" -> draft.copy(excludedInterestIds = draft.excludedInterestIds.toggled(), interestIds = draft.interestIds - id)
            else -> return
        }
        mutableState.value = current.copy(draft = updated)
    }
    fun next() {
        if (state.value.canContinue && state.value.step < 5) mutableState.value = state.value.copy(step = state.value.step + 1, error = null)
    }
    fun back() {
        if (!state.value.busy && state.value.step > 0) mutableState.value = state.value.copy(step = state.value.step - 1, error = null)
    }
    fun edit() {
        val current = state.value
        val profile = current.profile ?: return
        if (current.busy) return
        val options = current.options ?: return
        val draft = profile.copy(
            goalIds = profile.goalIds.intersect(options.goals.map { it.id }.toSet()),
            interestIds = profile.interestIds.intersect(options.interests.map { it.id }.toSet()),
            excludedInterestIds = profile.excludedInterestIds.intersect(options.interests.map { it.id }.toSet()),
            regionIds = profile.regionIds.intersect(options.regions.map { it.id }.toSet()))
        mutableState.value = current.copy(draft = draft, editing = true, step = 0,
            error = if (draft != profile) "Unavailable selections were removed from this draft. Review before saving." else null)
    }
    fun cancelEdit() {
        val current = state.value
        if (!current.busy && current.profile != null) mutableState.value = current.copy(draft = current.profile, editing = false, error = null)
    }
    fun save() {
        val current = state.value
        if (current.busy || !current.editing || current.step != 5 || current.draft.goalIds.isEmpty() ||
            current.draft.experience !in experienceChoices || current.draft.horizon !in horizonChoices) return
        execute {
            val saved = repository.save(current.draft, current.profile == null)
            mutableState.value = state.value.copy(profile = saved, draft = saved, editing = false, busy = false)
        }
    }
    private fun execute(action: suspend () -> Unit) {
        mutableState.value = state.value.copy(busy = true, error = null, consentRequired = false, sessionExpired = false)
        job = viewModelScope.launch {
            try { action() }
            catch (error: CancellationException) { throw error }
            catch (error: Exception) {
                val consent = error is HttpException && error.code() == 403
                val expired = error is SessionExpiredException
                mutableState.value = state.value.copy(busy = false, consentRequired = consent, sessionExpired = expired,
                    error = when {
                        consent -> "Please review the updated legal documents."
                        expired -> "Your session has expired. Please sign in again."
                        error is HttpException && error.code() == 422 -> "Some selections are unavailable. Reload your profile options."
                        else -> "Couldn’t load or save your profile. Your changes have not been confirmed. Please retry."
                    })
            }
        }
    }
}
