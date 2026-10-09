package app.yudy.data.auth

interface SessionAuthorizer {
    suspend fun <T> withAccessToken(request: suspend (String) -> T): T
}
