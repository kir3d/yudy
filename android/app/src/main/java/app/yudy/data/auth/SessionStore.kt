package app.yudy.data.auth

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.squareup.moshi.JsonDataException
import com.squareup.moshi.Moshi
import dagger.hilt.android.qualifiers.ApplicationContext
import java.security.GeneralSecurityException
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext

interface SessionStore {
    suspend fun read(): TokensDto?
    suspend fun readEmail(): String? = read()?.user?.email
    suspend fun write(tokens: TokensDto)
    suspend fun clear()
    suspend fun clearEmail() = Unit
}

private val Context.sessionDataStore by preferencesDataStore("session")

@Singleton
class KeystoreSessionStore @Inject constructor(
    @ApplicationContext private val context: Context,
    moshi: Moshi,
) : SessionStore {
    private val adapter = moshi.adapter(TokensDto::class.java)
    private val storedSession = stringPreferencesKey("encrypted_session")
    private val storedEmail = stringPreferencesKey("encrypted_email")
    private val keyAlias = "yudy.session.aes"

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(keyAlias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(keyAlias,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build())
            generateKey()
        }
    }

    private fun encrypt(value: String): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val bytes = cipher.iv + cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(bytes, Base64.NO_WRAP)
    }

    private fun decrypt(encoded: String): String {
        val bytes = Base64.decode(encoded, Base64.NO_WRAP)
        require(bytes.size > 12)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
        return String(cipher.doFinal(bytes.copyOfRange(12, bytes.size)), Charsets.UTF_8)
    }

    override suspend fun read(): TokensDto? = withContext(Dispatchers.IO) {
        val encoded = context.sessionDataStore.data.first()[storedSession] ?: return@withContext null
        try {
            adapter.fromJson(decrypt(encoded))
        } catch (_: GeneralSecurityException) {
            clear()
            null
        } catch (_: IllegalArgumentException) {
            clear()
            null
        } catch (_: JsonDataException) {
            clear()
            null
        }
    }

    override suspend fun readEmail(): String? = withContext(Dispatchers.IO) {
        val encoded = context.sessionDataStore.data.first()[storedEmail] ?: return@withContext null
        try {
            decrypt(encoded)
        } catch (_: GeneralSecurityException) {
            clearEmail()
            null
        } catch (_: IllegalArgumentException) {
            clearEmail()
            null
        }
    }

    override suspend fun write(tokens: TokensDto) = withContext(Dispatchers.IO) {
        val encryptedSession = encrypt(adapter.toJson(tokens))
        val encryptedEmail = encrypt(tokens.user.email)
        context.sessionDataStore.edit {
            it[storedSession] = encryptedSession
            it[storedEmail] = encryptedEmail
        }
        Unit
    }

    override suspend fun clear() {
        context.sessionDataStore.edit { it.remove(storedSession) }
    }

    override suspend fun clearEmail() {
        context.sessionDataStore.edit { it.remove(storedEmail) }
    }
}
