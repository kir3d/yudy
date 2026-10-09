package app.yudy.data.cache

import app.yudy.domain.assets.*
import app.yudy.domain.auth.*
import app.yudy.domain.profile.*
import app.yudy.domain.risk.*
import app.yudy.domain.legal.*
import kotlin.reflect.typeOf
import kotlin.reflect.jvm.javaType

class CachedAssets(private val remote: AssetRepository, private val cache: LocalCache): AssetRepository {
    override suspend fun filters() = cache.read("filters") { remote.filters() }
    override suspend fun catalog(query: CatalogQuery, cursor: String?) = cache.read("catalog:" + cache.moshi.adapter(CatalogQuery::class.java).toJson(query.copy(search = query.search.trim())) + ":" + cursor.orEmpty()) { remote.catalog(query, cursor) }
    override suspend fun details(id: String) = cache.read("asset:$id") { remote.details(id) }
    override suspend fun history(id: String, period: String) = cache.read("history:$id:$period") { remote.history(id, period) }
}
class CachedSelection(private val remote: SelectionRepository, private val cache: LocalCache): SelectionRepository {
    override suspend fun feed(cursor: String?) = cache.read("selection:" + cursor.orEmpty()) { remote.feed(cursor) }
    override suspend fun xstocks(forceRefresh: Boolean): XStockSelection {
        val key = "selection:xstocks"
        val maxAge = if (forceRefresh) -1L else 15 * 60 * 1000L
        return cache.readFresh(key, maxAge) { remote.xstocks(forceRefresh) }
    }
    override suspend fun catalog(search: String?, assetType: String?, sort: String, cursor: String?) =
        cache.readFresh("xstocks:catalog:${search.orEmpty()}:$assetType:$sort:${cursor.orEmpty()}", 5 * 60 * 1000L) {
            remote.catalog(search, assetType, sort, cursor)
        }
    override suspend fun savedXstocks() = cache.readFresh("xstocks:saved", 5 * 60 * 1000L) {
        remote.savedXstocks()
    }
    override suspend fun changeXstock(id: String, action: String, active: Boolean): InteractionState {
        cache.requireOnline()
        val result = remote.changeXstock(id, action, active)
        cache.invalidate("selection:xstocks")
        cache.invalidate("xstocks:catalog:")
        if (action == "save") cache.invalidate("xstocks:saved")
        return result
    }
    override suspend fun venues(id: String) = cache.readFresh("xstocks:venues:$id", 24 * 60 * 60 * 1000L) {
        remote.venues(id)
    }
    override suspend fun recordBuy(id: String, venue: String) {
        cache.requireOnline()
        remote.recordBuy(id, venue)
    }
}
@OptIn(ExperimentalStdlibApi::class)
class CachedInteractions(private val remote: InteractionRepository, private val cache: LocalCache): InteractionRepository {
    override suspend fun saved() = cache.read("saved") { remote.saved() }
    override suspend fun state(id: String) = cache.read("actions:$id") { remote.state(id) }
    override suspend fun change(id: String, action: String, active: Boolean): InteractionState {
        cache.requireOnline()
        val result = remote.change(id, action, active)
        // Confirmed mutations invalidate snapshots; a later offline read must not revive old flags.
        if(action == "save") cache.invalidate("saved")
        cache.invalidate("selection:")
        cache.put("actions:$id", typeOf<InteractionState>().javaType, result)
        return result
    }
}
@OptIn(ExperimentalStdlibApi::class)
class CachedProfile(private val remote: ProfileRepository, private val cache: LocalCache): ProfileRepository {
    override suspend fun options() = cache.read("profile-options") { remote.options() }
    override suspend fun load(): InvestorProfile? = cache.read("profile") { remote.load() }
    override suspend fun save(profile: InvestorProfile, onboarding: Boolean): InvestorProfile {
        cache.requireOnline(); val result = remote.save(profile, onboarding)
        cache.put("profile", typeOf<InvestorProfile?>().javaType, result)
        cache.invalidate("selection:")
        return result
    }
}
@OptIn(ExperimentalStdlibApi::class)
class CachedLegal(private val remote: LegalRepository, private val cache: LocalCache): LegalRepository {
    override suspend fun load() = cache.read("consent") { remote.load() }
    override suspend fun accept(documents: List<LegalDocument>): ConsentSnapshot {
        cache.requireOnline(); val result = remote.accept(documents)
        cache.put("consent", typeOf<ConsentSnapshot>().javaType, result); return result
    }
}
@OptIn(ExperimentalStdlibApi::class)
class CachedRisk(private val remote: RiskRepository, private val cache: LocalCache): RiskRepository {
    override suspend fun questions() = cache.read("risk-questions") { remote.questions() }
    override suspend fun load(): RiskResult? = cache.read("risk") { remote.load() }
    override suspend fun assess(version: String, answers: Map<String, String>): RiskResult {
        cache.requireOnline(); val result = remote.assess(version, answers)
        cache.put("risk", typeOf<RiskResult?>().javaType, result); cache.invalidate("selection:"); return result
    }
}
@OptIn(ExperimentalStdlibApi::class)
class CachedAuth(private val remote: AuthRepository, private val cache: LocalCache): AuthRepository {
    override suspend fun restore(): AuthUser? {
        if(cache.store.read() == null) return remote.restore()
        return try { cache.read("session") { remote.restore() } }
        catch(error: SessionExpiredException) { if(cache.store.read() == null) null else throw error }
    }
    override suspend fun rememberedEmail() = remote.rememberedEmail()
    override suspend fun register(email: String, password: String): AuthUser = remember(remote.register(email, password))
    override suspend fun login(email: String, password: String): AuthUser = remember(remote.login(email, password))
    private suspend fun remember(user: AuthUser): AuthUser { cache.put("session", typeOf<AuthUser?>().javaType, user); return user }
    override suspend fun logout() {
        val owner = cache.store.read()?.user?.id
        remote.logout()
        if(owner != null) cache.clear(owner)
    }
    override suspend fun deleteAccount() {
        val owner = cache.store.read()?.user?.id
        remote.deleteAccount()
        if(owner != null) cache.clear(owner)
    }
}
class CachedBuy(private val remote: BuyRepository, private val cache: LocalCache): BuyRepository {
    override suspend fun preview(assetId: String, tokenId: String): BuyLink { cache.requireOnline(); return remote.preview(assetId, tokenId) }
    override suspend fun confirm(assetId: String, tokenId: String, eventId: String): BuyLink { cache.requireOnline(); return remote.confirm(assetId, tokenId, eventId) }
}
