package app.yudy.di

import app.yudy.data.profile.ProfileApi
import app.yudy.data.profile.RemoteProfileRepository
import app.yudy.domain.profile.ProfileRepository
import app.yudy.data.risk.RiskApi
import app.yudy.data.risk.RemoteRiskRepository
import app.yudy.domain.risk.RiskRepository
import app.yudy.data.assets.AssetApi
import app.yudy.data.assets.RemoteAssetRepository
import app.yudy.domain.assets.AssetRepository
import app.yudy.data.assets.InteractionApi
import app.yudy.data.assets.RemoteInteractionRepository
import app.yudy.domain.assets.InteractionRepository
import app.yudy.data.assets.SelectionApi
import app.yudy.data.assets.RemoteSelectionRepository
import app.yudy.domain.assets.SelectionRepository
import app.yudy.data.learn.LearnApi
import app.yudy.data.learn.RemoteLearnRepository
import app.yudy.domain.learn.LearnRepository
import app.yudy.data.assets.BuyApi
import app.yudy.data.assets.RemoteBuyRepository
import app.yudy.domain.assets.BuyRepository
import app.yudy.BuildConfig
import app.yudy.data.auth.AuthApi
import app.yudy.data.auth.KeystoreSessionStore
import app.yudy.data.auth.RemoteAuthRepository
import app.yudy.data.auth.SessionStore
import app.yudy.data.auth.SessionAuthorizer
import app.yudy.data.legal.LegalApi
import app.yudy.data.legal.RemoteLegalRepository
import app.yudy.domain.legal.LegalRepository
import app.yudy.domain.auth.AuthRepository
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

@Module
@InstallIn(SingletonComponent::class)
abstract class AuthBindings {
    @Binds abstract fun sessionStore(implementation: KeystoreSessionStore): SessionStore
    @Binds abstract fun authorizer(implementation: RemoteAuthRepository): SessionAuthorizer
    @Binds abstract fun learnRepository(implementation: RemoteLearnRepository): LearnRepository
}

@Module
@InstallIn(SingletonComponent::class)
object AuthNetworkModule {
    @Provides @Singleton
    fun moshi(): Moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()

    @Provides @Singleton
    fun retrofit(moshi: Moshi): Retrofit {
        check(BuildConfig.API_BASE_URL.isNotBlank()) { "Configure API_BASE_URL for this build" }
        return Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(OkHttpClient.Builder()
                .connectTimeout(20, TimeUnit.SECONDS)
                .readTimeout(60, TimeUnit.SECONDS)
                .callTimeout(75, TimeUnit.SECONDS)
                .build())
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
    }

    @Provides @Singleton
    fun authApi(retrofit: Retrofit): AuthApi = retrofit.create(AuthApi::class.java)

    @Provides @Singleton
    fun legalApi(retrofit: Retrofit): LegalApi = retrofit.create(LegalApi::class.java)

    @Provides @Singleton
    fun profileApi(retrofit: Retrofit): ProfileApi = retrofit.create(ProfileApi::class.java)

    @Provides @Singleton
    fun riskApi(retrofit: Retrofit): RiskApi = retrofit.create(RiskApi::class.java)

    @Provides @Singleton
    fun interactionApi(retrofit: Retrofit): InteractionApi = retrofit.create(InteractionApi::class.java)

    @Provides @Singleton
    fun selectionApi(retrofit: Retrofit): SelectionApi = retrofit.create(SelectionApi::class.java)

    @Provides @Singleton
    fun learnApi(retrofit: Retrofit): LearnApi = retrofit.create(LearnApi::class.java)

    @Provides @Singleton
    fun buyApi(retrofit: Retrofit): BuyApi = retrofit.create(BuyApi::class.java)

    @Provides @Singleton
    fun assetApi(retrofit: Retrofit): AssetApi = retrofit.create(AssetApi::class.java)
}
