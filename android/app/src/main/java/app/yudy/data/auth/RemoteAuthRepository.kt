package app.yudy.data.auth

import app.yudy.domain.auth.AuthRepository
import app.yudy.domain.auth.AuthUser
import app.yudy.domain.auth.SessionExpiredException
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import retrofit2.HttpException

@Singleton
class RemoteAuthRepository @Inject constructor(
    private val api: AuthApi,
    private val store: SessionStore,
) : AuthRepository, SessionAuthorizer {
    private val mutex = Mutex()
    private var session: TokensDto? = null

    private suspend fun remember(tokens: TokensDto): AuthUser {
        store.write(tokens)
        session = tokens
        return AuthUser(tokens.user.id, tokens.user.email)
    }

    override suspend fun register(email: String, password: String): AuthUser = mutex.withLock {
        remember(api.register(CredentialsDto(email.trim(), password)).data)
    }

    override suspend fun login(email: String, password: String): AuthUser = mutex.withLock {
        remember(api.login(CredentialsDto(email.trim(), password)).data)
    }

    override suspend fun restore(): AuthUser? = mutex.withLock {
        val saved = store.read() ?: return@withLock null
        try {
            val user = api.me("Bearer ${saved.accessToken}").data
            session = saved
            AuthUser(user.id, user.email)
        } catch (error: HttpException) {
            if (error.code() != 401) throw error
            try {
                val renewed = api.refresh(RefreshDto(saved.refreshToken)).data
                remember(renewed)
            } catch (refreshError: HttpException) {
                if (refreshError.code() != 401) throw refreshError
                store.clear()
                session = null
                null
            }
        }
    }

    override suspend fun rememberedEmail(): String? = store.readEmail()

    override suspend fun logout() = mutex.withLock {
        val saved = session ?: store.read()
        if (saved != null) api.logout(RefreshDto(saved.refreshToken))
        store.clear()
        session = null
    }

    override suspend fun deleteAccount() = mutex.withLock {
        val saved = session ?: store.read() ?: throw SessionExpiredException()
        api.deleteAccount("Bearer ${saved.accessToken}")
        store.clear()
        store.clearEmail()
        session = null
    }

    override suspend fun <T> withAccessToken(request: suspend (String) -> T): T = mutex.withLock {
        val saved = session ?: store.read() ?: throw SessionExpiredException()
        try {
            request(saved.accessToken)
        } catch (error: HttpException) {
            if (error.code() != 401) throw error
            try {
                val renewed = api.refresh(RefreshDto(saved.refreshToken)).data
                remember(renewed)
                request(renewed.accessToken)
            } catch (refreshError: HttpException) {
                if (refreshError.code() != 401) throw refreshError
                store.clear()
                session = null
                throw SessionExpiredException()
            }
        }
    }
}
