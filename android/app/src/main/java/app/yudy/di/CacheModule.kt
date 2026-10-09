package app.yudy.di

import android.content.Context
import androidx.room.Room
import app.yudy.data.cache.*
import app.yudy.data.auth.*
import app.yudy.data.assets.*
import app.yudy.data.profile.RemoteProfileRepository
import app.yudy.data.risk.RemoteRiskRepository
import app.yudy.data.legal.RemoteLegalRepository
import app.yudy.domain.auth.AuthRepository
import app.yudy.domain.assets.*
import app.yudy.domain.profile.ProfileRepository
import app.yudy.domain.risk.RiskRepository
import app.yudy.domain.legal.LegalRepository
import com.squareup.moshi.Moshi
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object CacheModule {
    @Provides @Singleton fun database(@ApplicationContext context: Context): CacheDatabase = Room.databaseBuilder(context, CacheDatabase::class.java, "yudy-cache.db").build()
    @Provides @Singleton fun cache(db: CacheDatabase, store: SessionStore, moshi: Moshi) = LocalCache(db.entries(), store, moshi)
    @Provides @Singleton fun auth(remote: RemoteAuthRepository, cache: LocalCache): AuthRepository = CachedAuth(remote, cache)
    @Provides @Singleton fun assets(remote: RemoteAssetRepository, cache: LocalCache): AssetRepository = CachedAssets(remote, cache)
    @Provides @Singleton fun selection(remote: RemoteSelectionRepository, cache: LocalCache): SelectionRepository = CachedSelection(remote, cache)
    @Provides @Singleton fun interactions(remote: RemoteInteractionRepository, cache: LocalCache): InteractionRepository = CachedInteractions(remote, cache)
    @Provides @Singleton fun profile(remote: RemoteProfileRepository, cache: LocalCache): ProfileRepository = CachedProfile(remote, cache)
    @Provides @Singleton fun risk(remote: RemoteRiskRepository, cache: LocalCache): RiskRepository = CachedRisk(remote, cache)
    @Provides @Singleton fun legal(remote: RemoteLegalRepository, cache: LocalCache): LegalRepository = CachedLegal(remote, cache)
    @Provides @Singleton fun buy(remote: RemoteBuyRepository, cache: LocalCache): BuyRepository = CachedBuy(remote, cache)
}
