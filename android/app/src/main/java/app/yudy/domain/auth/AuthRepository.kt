package app.yudy.domain.auth

data class AuthUser(val id: String, val email: String)

class SessionExpiredException : Exception("Your session has expired")

interface AuthRepository {
    suspend fun restore(): AuthUser?
    suspend fun rememberedEmail(): String? = null
    suspend fun register(email: String, password: String): AuthUser
    suspend fun login(email: String, password: String): AuthUser
    suspend fun logout()
    suspend fun deleteAccount()
}
