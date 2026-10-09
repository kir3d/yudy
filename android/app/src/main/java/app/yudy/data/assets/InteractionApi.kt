package app.yudy.data.assets

import app.yudy.data.auth.ApiData
import app.yudy.data.auth.SessionAuthorizer
import app.yudy.domain.assets.*
import javax.inject.Inject
import retrofit2.http.*

interface InteractionApi {
    @GET("api/v1/assets/{id}/interactions") suspend fun state(@Header("Authorization") token: String, @Path("id") id: String): ApiData<InteractionState>
    @POST("api/v1/assets/{id}/{action}") suspend fun enable(@Header("Authorization") token: String, @Path("id") id: String, @Path("action") action: String): ApiData<InteractionState>
    @DELETE("api/v1/assets/{id}/{action}") suspend fun disable(@Header("Authorization") token: String, @Path("id") id: String, @Path("action") action: String): ApiData<InteractionState>
    @GET("api/v1/saved") suspend fun saved(@Header("Authorization") token: String): ApiData<List<AssetDto>>
}
class RemoteInteractionRepository @Inject constructor(private val api: InteractionApi, private val authorizer: SessionAuthorizer): InteractionRepository {
    override suspend fun state(id: String) = authorizer.withAccessToken { api.state("Bearer $it", id).data }
    override suspend fun change(id: String, action: String, active: Boolean) = authorizer.withAccessToken {
        (if (active) api.enable("Bearer $it", id, action) else api.disable("Bearer $it", id, action)).data
    }
    override suspend fun saved() = authorizer.withAccessToken { api.saved("Bearer $it").data.map { asset -> asset.summary() } }
}
