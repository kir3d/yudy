package app.yudy.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.yudy.domain.auth.AuthRepository
import app.yudy.domain.auth.AuthUser
import dagger.hilt.android.lifecycle.HiltViewModel
import java.io.IOException
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class AuthUiState(
    val user: AuthUser? = null,
    val busy: Boolean = true,
    val email: String = "",
    val password: String = "",
    val error: String? = null,
    val restoring: Boolean = true,
) {
    override fun toString() = "AuthUiState(busy=$busy, restoring=$restoring, redacted)"
}

@HiltViewModel
class AuthViewModel @Inject constructor(private val repository: AuthRepository) : ViewModel() {
    private val mutableState = MutableStateFlow(AuthUiState())
    val state = mutableState.asStateFlow()

    init { restore() }

    fun emailChanged(value: String) {
        mutableState.value = state.value.copy(email = value, error = null)
    }

    fun passwordChanged(value: String) {
        mutableState.value = state.value.copy(password = value, error = null)
    }

    fun clearForm() {
        mutableState.value = state.value.copy(password = "", error = null)
    }

    fun restore() = runOperation(restoring = true) { repository.restore() }

    fun submit(register: Boolean) {
        if (state.value.busy) return
        val email = state.value.email.trim()
        val password = state.value.password
        if (email.isBlank() || password.length !in 10..128) {
            mutableState.value = state.value.copy(error = "Enter an email and a password of 10–128 characters.")
            return
        }
        runOperation {
            if (register) repository.register(email, password) else repository.login(email, password)
        }
    }

    fun logout() {
        if (state.value.busy) return
        runOperation { repository.logout(); null }
    }

    fun deleteAccount() {
        if (state.value.busy) return
        runOperation { repository.deleteAccount(); null }
    }

    private fun runOperation(restoring: Boolean = false, action: suspend () -> AuthUser?) {
        mutableState.value = state.value.copy(busy = true, error = null, restoring = restoring)
        viewModelScope.launch {
            try {
                val user = action()
                val email = if (restoring) user?.email ?: repository.rememberedEmail().orEmpty()
                    else user?.email ?: state.value.email
                mutableState.value = state.value.copy(user = user, email = email, password = "",
                    busy = false, restoring = false)
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                val email = if (restoring) {
                    try { repository.rememberedEmail().orEmpty() } catch (_: Exception) { state.value.email }
                } else state.value.email
                val message = when (error) {
                    is HttpException -> when (error.code()) {
                        401 -> "Invalid email or password. Accounts from earlier test builds need to be created once for yudyai.xyz."
                        403 -> "This account’s email is not confirmed. Confirm it before signing in."
                        409 -> "This email is already registered. Sign in instead."
                        422 -> "Check your email and password."
                        429 -> "Too many attempts. Please try again in a minute."
                        else -> "The service is unavailable. Please try again."
                    }
                    is IOException -> "Couldn’t connect. Check your internet connection and try again."
                    else -> "Couldn’t complete the request. Please try again."
                }
                mutableState.value = state.value.copy(busy = false, error = message, email = email,
                    password = "", restoring = restoring)
            }
        }
    }
}
