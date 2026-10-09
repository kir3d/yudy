package app.yudy.data.cache

import app.yudy.data.auth.SessionStore
import app.yudy.domain.auth.SessionExpiredException
import com.squareup.moshi.Moshi
import java.io.IOException
import java.lang.reflect.Type
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlin.reflect.typeOf
import kotlin.reflect.jvm.javaType
import retrofit2.HttpException

class OfflineWriteException: IOException("Cached data is read-only. Reconnect and reload before making changes.")
data class CacheStatus(val owner: String? = null, val stale: Map<String, Long> = emptyMap(), val generation: Int = 0) {
    val readOnly: Boolean get() = stale.isNotEmpty()
}
class LocalCache(val dao: CacheDao, val store: SessionStore, val moshi: Moshi) {
    private val mutable = MutableStateFlow(CacheStatus())
    val status = mutable.asStateFlow()
    suspend fun owner(): String {
        val id = store.read()?.user?.id ?: throw SessionExpiredException()
        if(status.value.owner != id) mutable.value = CacheStatus(owner = id, generation = status.value.generation)
        return id
    }
    fun requireOnline() { if(status.value.readOnly) throw OfflineWriteException() }
    fun reconnect() { mutable.value = CacheStatus(owner = status.value.owner, generation = status.value.generation + 1) }
    suspend fun clear(owner: String) { dao.clear(owner); if(status.value.owner == owner) mutable.value = status.value.copy(stale = emptyMap()) }
    suspend fun invalidate(prefix: String) { dao.deletePrefix(owner(), prefix); mutable.value = status.value.copy(stale = status.value.stale.filterKeys { !it.startsWith(prefix) }) }
    fun fresh(key: String) { mutable.value = status.value.copy(stale = status.value.stale - key) }
    suspend fun <T> put(key: String, type: Type, value: T) {
        val id = owner(); dao.put(CacheEntry(id, key, moshi.adapter<T>(type).toJson(value), System.currentTimeMillis())); if(store.read()?.user?.id != id) { clear(id); throw SessionExpiredException() }; fresh(key)
    }
    @OptIn(ExperimentalStdlibApi::class)
    suspend inline fun <reified T> read(key: String, noinline request: suspend () -> T): T = read(key, typeOf<T>().javaType, request)
    @OptIn(ExperimentalStdlibApi::class)
    suspend inline fun <reified T> readFresh(key: String, maxAgeMillis: Long,
        noinline request: suspend () -> T): T = readFresh(key, typeOf<T>().javaType, maxAgeMillis, request)
    suspend fun <T> readFresh(key: String, type: Type, maxAgeMillis: Long,
        request: suspend () -> T): T {
        val id = owner()
        val entry = dao.get(id, key)
        if (entry != null && System.currentTimeMillis() - entry.savedAt <= maxAgeMillis) {
            val cached = moshi.adapter<T>(type).fromJson(entry.json)
            if (cached != null) {
                fresh(key)
                return cached
            }
        }
        return read(key, type, request)
    }
    suspend fun <T> read(key: String, type: Type, request: suspend () -> T): T {
        val id = owner()
        val value: T = try { request() }
        catch(error: IOException) {
            if(store.read()?.user?.id != id) throw SessionExpiredException()
            val entry = dao.get(id, key) ?: throw error
            if(store.read()?.user?.id != id) throw SessionExpiredException()
            val cached = moshi.adapter<T>(type).fromJson(entry.json)
            mutable.value = status.value.copy(stale = status.value.stale + (key to entry.savedAt))
            @Suppress("UNCHECKED_CAST") return cached as T
        } catch(error: HttpException) {
            if(error.code() in listOf(401, 403)) clear(id)
            else if(error.code() in listOf(404, 409)) { dao.delete(id, key); fresh(key) }
            throw error
        } catch(error: SessionExpiredException) { clear(id); throw error }
        if(store.read()?.user?.id != id) { clear(id); throw SessionExpiredException() }
        put(key, type, value)
        return value
    }
}
