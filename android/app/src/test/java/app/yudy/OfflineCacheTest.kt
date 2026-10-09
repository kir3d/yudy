package app.yudy

import app.yudy.data.auth.*
import app.yudy.data.cache.*
import app.yudy.domain.auth.*
import app.yudy.domain.assets.*
import app.yudy.domain.profile.*
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import java.io.IOException
import kotlinx.coroutines.*
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test
import okhttp3.ResponseBody.Companion.toResponseBody
import retrofit2.HttpException
import retrofit2.Response

class TestCacheDao: CacheDao {
    val rows = mutableMapOf<Pair<String, String>, CacheEntry>()
    override suspend fun get(owner: String, key: String) = rows[owner to key]
    override suspend fun put(entry: CacheEntry) { rows[entry.owner to entry.key] = entry }
    override suspend fun delete(owner: String, key: String) { rows.remove(owner to key) }
    override suspend fun deletePrefix(owner: String, prefix: String) { rows.keys.filter { it.first == owner && it.second.startsWith(prefix) }.forEach { rows.remove(it) } }
    override suspend fun clear(owner: String) { rows.keys.filter { it.first == owner }.forEach { rows.remove(it) } }
}
class TestCacheSession: SessionStore {
    var tokens: TokensDto? = TokensDto("access", "refresh", UserDto("first", "first@example.test"))
    override suspend fun read() = tokens
    override suspend fun write(tokens: TokensDto) { this.tokens = tokens }
    override suspend fun clear() { tokens = null }
}
class OfflineCacheTest {
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
    private class CacheAuthRemote(private val store: TestCacheSession): AuthRepository {
        var offline = false
        var expired = false
        override suspend fun restore(): AuthUser? {
            if(offline) throw IOException()
            if(expired) { store.clear(); return null }
            return store.read()?.user?.let { AuthUser(it.id, it.email) }
        }
        override suspend fun login(email: String, password: String) = restore()!!
        override suspend fun register(email: String, password: String) = login(email, password)
        override suspend fun logout() { if(offline) throw IOException(); store.clear() }
        override suspend fun deleteAccount() { if(offline) throw IOException(); store.clear() }
    }
    @Test fun offlineSessionRestoresOnlyPreviouslyConfirmedUser() = runTest {
        val dao = TestCacheDao(); val store = TestCacheSession(); val remote = CacheAuthRemote(store)
        val repo = CachedAuth(remote, LocalCache(dao, store, moshi))
        val user = repo.restore()
        remote.offline = true
        val reopened = LocalCache(dao, store, moshi)
        assertEquals(user, CachedAuth(remote, reopened).restore())
        assertTrue(reopened.status.value.readOnly)
        assertNotNull(store.read())
        store.clear()
        try { CachedAuth(remote, reopened).restore(); fail("No offline identity without credentials") } catch(expected: IOException) { }
    }
    @Test fun confirmedSessionExpiryPurgesPrivateCache() = runTest {
        val dao = TestCacheDao(); val store = TestCacheSession(); val remote = CacheAuthRemote(store)
        val cache = LocalCache(dao, store, moshi); val repo = CachedAuth(remote, cache)
        repo.restore(); cache.read("saved") { listOf(demoAsset()) }
        remote.expired = true
        assertNull(repo.restore()); assertNull(store.read()); assertTrue(dao.rows.isEmpty())
    }
    @Test fun logoutClearsCacheOnlyAfterConfirmedRemoteLogout() = runTest {
        val dao = TestCacheDao(); val store = TestCacheSession(); val remote = CacheAuthRemote(store)
        val repo = CachedAuth(remote, LocalCache(dao, store, moshi))
        repo.restore(); remote.offline = true
        try { repo.logout(); fail("Must report unconfirmed logout") } catch(expected: IOException) { }
        assertNotNull(store.read()); assertFalse(dao.rows.isEmpty())
        remote.offline = false; repo.logout()
        assertNull(store.read()); assertTrue(dao.rows.isEmpty())
    }
    @Test fun networkFirstPersistsAcrossCacheRecreationAndMarksStale() = runTest {
        val dao = TestCacheDao(); val store = TestCacheSession(); val cache = LocalCache(dao, store, moshi)
        val detail = demoDetail("one")
        assertEquals(detail, cache.read("asset:one") { detail })
        assertFalse(cache.status.value.readOnly)
        val reopened = LocalCache(dao, store, moshi)
        val cached = reopened.read<AssetDetails>("asset:one") { throw IOException("offline") }
        assertEquals(detail, cached); assertTrue(reopened.status.value.readOnly)
        assertEquals(dao.rows["first" to "asset:one"]!!.savedAt, reopened.status.value.stale["asset:one"])
        reopened.read("asset:one") { detail }; assertFalse(reopened.status.value.readOnly)
    }
    @Test fun cacheMissDoesNotFabricateData() = runTest {
        val cache = LocalCache(TestCacheDao(), TestCacheSession(), moshi)
        try { cache.read<AssetDetails>("missing") { throw IOException() }; fail("Must fail") } catch(expected: IOException) { }
        assertFalse(cache.status.value.readOnly)
    }
    @Test fun accountSwitchNeverReturnsAnotherUsersPrivateData() = runTest {
        val dao = TestCacheDao(); val store = TestCacheSession(); val cache = LocalCache(dao, store, moshi)
        cache.read("profile") { InvestorProfile(experience = "NEW", goalIds = setOf("goal")) }
        store.tokens = store.tokens!!.copy(user = UserDto("second", "second@example.test"))
        try { cache.read<InvestorProfile>("profile") { throw IOException() }; fail("Must isolate") } catch(expected: IOException) { }
        assertNotNull(dao.rows["first" to "profile"]); assertEquals("second", cache.status.value.owner)
    }
    @Test fun authErrorsPurgeCacheAndNeverFallBack() = runTest {
        for(code in listOf(401, 403)) {
            val dao = TestCacheDao(); val cache = LocalCache(dao, TestCacheSession(), moshi)
            cache.read("saved") { listOf(demoAsset()) }
            try { cache.read<List<AssetSummary>>("saved") { throw HttpException(Response.error<Any>(code, "{}".toResponseBody())) }; fail("Must reject") }
            catch(error: HttpException) { assertEquals(code, error.code()) }
            assertTrue(dao.rows.isEmpty())
        }
    }
    @Test fun unavailableAssetPurgesOnlyItsEntryAndCancellationDoesNotFallback() = runTest {
        val dao = TestCacheDao(); val cache = LocalCache(dao, TestCacheSession(), moshi)
        cache.read("asset:one") { demoDetail("one") }; cache.read("asset:two") { demoDetail("two") }
        try { cache.read<AssetDetails>("asset:one") { throw HttpException(Response.error<Any>(404, "{}".toResponseBody())) }; fail("Must reject") } catch(expected: HttpException) { }
        assertNull(dao.rows["first" to "asset:one"]); assertNotNull(dao.rows["first" to "asset:two"])
        try { cache.read<AssetDetails>("asset:two") { throw CancellationException() }; fail("Must cancel") } catch(expected: CancellationException) { }
        assertFalse(cache.status.value.readOnly)
    }
    @Test fun nullProfileAndEmptySavedAreRealCachedValues() = runTest {
        val cache = LocalCache(TestCacheDao(), TestCacheSession(), moshi)
        cache.read<InvestorProfile?>("profile") { null }; cache.read<List<AssetSummary>>("saved") { emptyList() }
        assertNull(cache.read<InvestorProfile?>("profile") { throw IOException() })
        assertTrue(cache.read<List<AssetSummary>>("saved") { throw IOException() }.isEmpty())
        assertTrue(cache.status.value.readOnly)
    }
    @Test fun offlineWritesBlockedUntilExplicitReconnect() = runTest {
        val cache = LocalCache(TestCacheDao(), TestCacheSession(), moshi)
        cache.read("saved") { listOf(demoAsset()) }; cache.read<List<AssetSummary>>("saved") { throw IOException() }
        try { cache.requireOnline(); fail("Must block") } catch(expected: OfflineWriteException) { }
        cache.reconnect(); cache.requireOnline(); assertEquals(1, cache.status.value.generation)
    }
    @Test fun userChangesDuringRequestDoNotPersistOldResponse() = runTest {
        val dao = TestCacheDao(); val store = TestCacheSession(); val cache = LocalCache(dao, store, moshi)
        try { cache.read("profile") { store.tokens = store.tokens!!.copy(user = UserDto("second", "second@example.test")); InvestorProfile() }; fail("Must cancel") }
        catch(expected: SessionExpiredException) { }
        assertTrue(dao.rows.isEmpty())
    }
    @Test fun confirmedReactionsInvalidateEveryFeedPageButKeepSavedIndependent() = runTest {
        val dao = TestCacheDao(); val cache = LocalCache(dao, TestCacheSession(), moshi)
        cache.read("selection:") { "first" }; cache.read("selection:next") { "second" }; cache.read("saved") { listOf(demoAsset()) }
        val remote = FakeInteractionRepository()
        val repo = CachedInteractions(remote, cache)
        repo.change("one", "like", true)
        assertFalse(dao.rows.keys.any { it.second.startsWith("selection:") })
        assertNotNull(dao.rows["first" to "saved"])
        remote.failure = IOException()
        assertTrue(repo.state("one").liked); assertEquals(1, repo.saved().size)
    }
    @Test fun cachedAssetQueryKeysAndHistoryPeriodsRemainSeparate() = runTest {
        val dao = TestCacheDao(); val store = TestCacheSession(); val cache = LocalCache(dao, store, moshi)
        val remote = FakeAssetRepository(); val repo = CachedAssets(remote, cache)
        val original = repo.catalog(CatalogQuery(search = "first")); repo.history("one", "1Y")
        remote.failure = IOException(); remote.historyFailure = IOException()
        assertEquals(original, repo.catalog(CatalogQuery(search = "first")))
        try { repo.catalog(CatalogQuery(search = "second")); fail("Do not reuse filters") } catch(expected: IOException) { }
        assertEquals("1Y", repo.history("one", "1Y").period)
        try { repo.history("one", "3Y"); fail("Do not reuse period") } catch(expected: IOException) { }
    }
    @Test fun xstocksSelectionUsesFreshCacheUntilExplicitRefresh() = runTest {
        val remote = FakeSelectionRepository()
        val repo = CachedSelection(remote, LocalCache(TestCacheDao(), TestCacheSession(), moshi))
        assertEquals("AAPLx", repo.xstocks().items.single().symbol)
        remote.current = remote.current.copy(items = listOf(xstock("SPYx")))
        assertEquals("AAPLx", repo.xstocks().items.single().symbol)
        assertEquals(1, remote.calls)
        assertEquals("SPYx", repo.xstocks(forceRefresh = true).items.single().symbol)
        assertEquals(2, remote.calls)
    }
}
