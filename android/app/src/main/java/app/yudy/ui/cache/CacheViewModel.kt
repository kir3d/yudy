package app.yudy.ui.cache

import androidx.lifecycle.ViewModel
import app.yudy.data.cache.LocalCache
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

@HiltViewModel
class CacheViewModel @Inject constructor(private val cache: LocalCache): ViewModel() {
    val status = cache.status
    fun reconnect() = cache.reconnect()
}
