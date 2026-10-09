package app.yudy

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.yudy.data.auth.KeystoreSessionStore
import app.yudy.data.auth.TokensDto
import app.yudy.data.auth.UserDto
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class KeystoreSessionStoreTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
    private val store = KeystoreSessionStore(context, moshi)

    @Before fun reset() = runBlocking {
        store.clear()
        store.clearEmail()
    }

    @After fun cleanup() = reset()

    @Test fun sessionAndEmailSurviveStoreRecreationWithoutPersistingPassword() = runBlocking {
        store.write(TokensDto("access", "refresh", UserDto("user-1", "test@example.com")))

        val reopened = KeystoreSessionStore(context, moshi)
        assertEquals("refresh", reopened.read()!!.refreshToken)
        assertEquals("test@example.com", reopened.readEmail())

        reopened.clear()
        assertNull(reopened.read())
        assertEquals("test@example.com", reopened.readEmail())

        reopened.clearEmail()
        assertNull(reopened.readEmail())
    }
}
