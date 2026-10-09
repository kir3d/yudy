package app.yudy

import app.yudy.domain.auth.AuthRepository
import app.yudy.domain.auth.AuthUser
import app.yudy.ui.auth.AuthViewModel
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

private class FakeAuthRepository : AuthRepository {
    var restored: AuthUser? = null
    var remembered: String? = null
    var calls = 0
    var restoreError: IOException? = null
    override suspend fun restore(): AuthUser? {
        restoreError?.let { throw it }
        return restored
    }
    override suspend fun rememberedEmail() = remembered
    override suspend fun register(email: String, password: String): AuthUser {
        calls++
        return AuthUser("user-1", email)
    }
    override suspend fun login(email: String, password: String) = register(email, password)
    override suspend fun logout() { restored = null }
    override suspend fun deleteAccount() { restored = null }
}

@OptIn(ExperimentalCoroutinesApi::class)
class AuthViewModelTest {
    @Before fun setup() { Dispatchers.setMain(UnconfinedTestDispatcher()) }
    @After fun cleanup() { Dispatchers.resetMain() }

    @Test fun emptySessionRequiresAuthentication() {
        val model = AuthViewModel(FakeAuthRepository())
        assertNull(model.state.value.user)
        assertFalse(model.state.value.busy)
        assertFalse(model.state.value.restoring)
    }

    @Test fun startupRestoresSavedSessionWithoutPassword() {
        val repository = FakeAuthRepository().apply {
            restored = AuthUser("user-1", "test@example.com")
        }
        val model = AuthViewModel(repository)
        assertEquals("user-1", model.state.value.user!!.id)
        assertEquals("test@example.com", model.state.value.email)
        assertEquals("", model.state.value.password)
        assertFalse(model.state.value.restoring)
    }

    @Test fun expiredSessionPrefillsEncryptedRememberedEmail() {
        val repository = FakeAuthRepository().apply { remembered = "test@example.com" }
        val model = AuthViewModel(repository)
        assertNull(model.state.value.user)
        assertEquals("test@example.com", model.state.value.email)
        assertEquals("", model.state.value.password)
    }

    @Test fun invalidFormDoesNotCallRepository() {
        val repository = FakeAuthRepository()
        val model = AuthViewModel(repository)
        model.emailChanged("test@example.com")
        model.passwordChanged("short")
        model.submit(true)
        assertEquals(0, repository.calls)
        assertNotNull(model.state.value.error)
    }

    @Test fun registrationSignsInAndClearsPassword() {
        val model = AuthViewModel(FakeAuthRepository())
        model.emailChanged(" test@example.com ")
        model.passwordChanged("long-password")
        model.submit(true)
        assertEquals("test@example.com", model.state.value.user!!.email)
        assertEquals("", model.state.value.password)
        assertFalse(model.state.value.busy)
    }

    @Test fun failedRestoreDoesNotOpenProtectedScreen() {
        val repository = FakeAuthRepository().apply { restoreError = IOException("offline") }
        val model = AuthViewModel(repository)
        assertNull(model.state.value.user)
        assertTrue(model.state.value.restoring)
        assertNotNull(model.state.value.error)
        repository.restoreError = null
        repository.restored = AuthUser("user-1", "test@example.com")
        model.restore()
        assertNotNull(model.state.value.user)
    }

    @Test fun logoutReturnsToUnauthenticatedState() {
        val repository = FakeAuthRepository().apply {
            restored = AuthUser("user-1", "test@example.com")
        }
        val model = AuthViewModel(repository)
        model.logout()
        assertNull(model.state.value.user)
        assertFalse(model.state.value.busy)
    }

    @Test fun deleteAccountReturnsToUnauthenticatedState() {
        val repository = FakeAuthRepository().apply {
            restored = AuthUser("user-1", "test@example.com")
        }
        val model = AuthViewModel(repository)
        model.deleteAccount()
        assertNull(model.state.value.user)
        assertFalse(model.state.value.busy)
    }
}
