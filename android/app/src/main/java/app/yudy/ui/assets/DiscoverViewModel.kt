package app.yudy.ui.assets

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.yudy.domain.assets.*
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class DiscoverUiState(val searchText: String = "", val search: String = "",
    val assetType: String? = null, val sort: String = "symbol",
    val items: List<XStockSuggestion> = emptyList(), val total: Int = 0,
    val nextCursor: String? = null, val busy: Boolean = true, val loadingMore: Boolean = false,
    val error: String? = null, val pageError: String? = null, val actionError: String? = null,
    val changing: Set<String> = emptySet(), val consentRequired: Boolean = false,
    val sessionExpired: Boolean = false)

@HiltViewModel
class DiscoverViewModel @Inject constructor(private val repository: SelectionRepository) : ViewModel() {
    private val mutableState = MutableStateFlow(DiscoverUiState())
    val state = mutableState.asStateFlow()
    private var userId: String? = null
    private var job: Job? = null
    fun bindUser(id: String) {
        if (id != userId) { clear(); userId = id }
        reload()
    }
    fun clear() { job?.cancel(); userId = null; mutableState.value = DiscoverUiState() }
    fun searchText(value: String) { mutableState.value = state.value.copy(searchText = value.take(100)) }
    fun search() = apply(state.value.assetType, state.value.sort, state.value.searchText.trim())
    fun apply(assetType: String?, sort: String, search: String = state.value.search) {
        if (userId == null) return
        mutableState.value = state.value.copy(assetType = assetType, sort = sort, search = search,
            searchText = search)
        reload()
    }
    fun resetFilters() = apply(null, "symbol", "")
    fun reload() {
        if (userId == null) return
        job?.cancel()
        mutableState.value = state.value.copy(items = emptyList(), total = 0, nextCursor = null,
            busy = true, loadingMore = false, error = null, pageError = null,
            consentRequired = false, sessionExpired = false)
        job = viewModelScope.launch {
            try {
                val page = repository.catalog(state.value.search.takeIf(String::isNotBlank),
                    state.value.assetType, state.value.sort)
                mutableState.value = state.value.copy(items = page.items, total = page.total,
                    nextCursor = page.nextCursor, busy = false)
            } catch (error: CancellationException) { throw error }
            catch (error: Exception) { mutableState.value = state.value.copy(busy = false,
                error = "Couldn’t load the live xStocks catalog. Please retry.",
                consentRequired = error is HttpException && error.code() == 403,
                sessionExpired = error is app.yudy.domain.auth.SessionExpiredException) }
        }
    }
    fun loadMore() {
        val current = state.value
        val cursor = current.nextCursor ?: return
        if (current.busy || current.loadingMore) return
        mutableState.value = current.copy(loadingMore = true, pageError = null)
        job = viewModelScope.launch {
            try {
                val page = repository.catalog(current.search.takeIf(String::isNotBlank),
                    current.assetType, current.sort, cursor)
                mutableState.value = state.value.copy(items = (current.items + page.items).distinctBy { it.id },
                    total = page.total, nextCursor = page.nextCursor, loadingMore = false)
            } catch (error: CancellationException) { throw error }
            catch (error: Exception) { mutableState.value = state.value.copy(loadingMore = false,
                pageError = if (error is HttpException && error.code() == 400)
                    "The catalog changed. Reload the results to continue." else "Couldn’t load the next page. Please retry.") }
        }
    }
    fun change(item: XStockSuggestion, action: String) {
        if (item.id in state.value.changing) return
        val active = when (action) {
            "like" -> !item.interaction.liked
            "dislike" -> !item.interaction.disliked
            "save" -> !item.interaction.saved
            else -> return
        }
        mutableState.value = state.value.copy(changing = state.value.changing + item.id,
            actionError = null)
        viewModelScope.launch {
            try {
                val updated = repository.changeXstock(item.id, action, active)
                mutableState.value = state.value.copy(
                    items = state.value.items.map { if (it.id == item.id) it.copy(interaction = updated) else it },
                    changing = state.value.changing - item.id,
                )
            } catch (error: CancellationException) { throw error }
            catch (error: Exception) {
                mutableState.value = state.value.copy(changing = state.value.changing - item.id,
                    actionError = "Could not update this action. Please try again.",
                    consentRequired = error is HttpException && error.code() == 403,
                    sessionExpired = error is app.yudy.domain.auth.SessionExpiredException)
            }
        }
    }
}
