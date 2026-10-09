package app.yudy.domain.assets

data class InteractionState(val liked: Boolean = false, val disliked: Boolean = false, val saved: Boolean = false)
interface InteractionRepository {
    suspend fun state(id: String): InteractionState
    suspend fun change(id: String, action: String, active: Boolean): InteractionState
    suspend fun saved(): List<AssetSummary>
}
