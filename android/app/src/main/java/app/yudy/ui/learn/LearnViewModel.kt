package app.yudy.ui.learn

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.yudy.domain.learn.*
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import retrofit2.HttpException

data class LearnUiState(val articles: List<LearnArticle> = emptyList(), val busy: Boolean = true,
    val error: String? = null, val slug: String? = null, val article: LearnArticle? = null,
    val articleBusy: Boolean = false, val articleError: String? = null)
@HiltViewModel
class LearnViewModel @Inject constructor(private val repository: LearnRepository): ViewModel() {
    private val mutable = MutableStateFlow(LearnUiState())
    val state = mutable.asStateFlow()
    private var listJob: Job? = null
    private var articleJob: Job? = null
    fun clear() { listJob?.cancel(); articleJob?.cancel(); mutable.value = LearnUiState() }
    fun reload() {
        listJob?.cancel(); mutable.value = state.value.copy(articles = emptyList(), busy = true, error = null)
        listJob = viewModelScope.launch {
            try { mutable.value = state.value.copy(articles = repository.articles(), busy = false) }
            catch(error: Exception) {
                if(error is CancellationException) throw error
                mutable.value = state.value.copy(busy = false, error = "Could not load Learn. Please retry.")
            }
        }
    }
    fun open(slug: String) {
        articleJob?.cancel()
        mutable.value = state.value.copy(slug = slug, article = null, articleBusy = true, articleError = null)
        articleJob = viewModelScope.launch {
            try { mutable.value = state.value.copy(article = repository.article(slug), articleBusy = false) }
            catch(error: Exception) {
                if(error is CancellationException) throw error
                mutable.value = state.value.copy(articleBusy = false, articleError = if(error is HttpException && error.code() == 404) "This article is unavailable." else "Could not load the article. Please retry.")
            }
        }
    }
    fun closeArticle() { articleJob?.cancel(); mutable.value = state.value.copy(slug = null, article = null, articleBusy = false, articleError = null) }
}
