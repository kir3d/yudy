package app.yudy.data.auth

import com.squareup.moshi.Json
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.DELETE

data class CredentialsDto(val email: String, val password: String) {
    override fun toString() = "CredentialsDto(redacted)"
}
data class RefreshDto(@Json(name = "refresh_token") val refreshToken: String) {
    override fun toString() = "RefreshDto(redacted)"
}
data class UserDto(val id: String, val email: String)
data class TokensDto(
    @Json(name = "access_token") val accessToken: String,
    @Json(name = "refresh_token") val refreshToken: String,
    val user: UserDto,
) {
    override fun toString() = "TokensDto(redacted)"
}
data class ApiData<T>(val data: T)

interface AuthApi {
    @POST("api/v1/auth/register")
    suspend fun register(@Body body: CredentialsDto): ApiData<TokensDto>
    @POST("api/v1/auth/login")
    suspend fun login(@Body body: CredentialsDto): ApiData<TokensDto>
    @POST("api/v1/auth/refresh")
    suspend fun refresh(@Body body: RefreshDto): ApiData<TokensDto>
    @POST("api/v1/auth/logout")
    suspend fun logout(@Body body: RefreshDto)
    @GET("api/v1/users/me")
    suspend fun me(@Header("Authorization") authorization: String): ApiData<UserDto>
    @DELETE("api/v1/users/me")
    suspend fun deleteAccount(@Header("Authorization") authorization: String)
}
