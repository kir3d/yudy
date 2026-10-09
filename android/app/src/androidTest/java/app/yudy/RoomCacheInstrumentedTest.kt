package app.yudy

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.yudy.data.cache.CacheDatabase
import app.yudy.data.cache.CacheEntry
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class RoomCacheInstrumentedTest {
    @Test fun persistenceAndOwnerScopedInvalidation() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val name = "cache-test-${UUID.randomUUID()}.db"
        var db = Room.databaseBuilder(context, CacheDatabase::class.java, name).build()
        try {
            db.entries().put(CacheEntry("first", "selection:", "[]", 42))
            db.entries().put(CacheEntry("first", "selection:next", "[]", 43))
            db.entries().put(CacheEntry("second", "selection:", "[1]", 44))
            db.close()
            db = Room.databaseBuilder(context, CacheDatabase::class.java, name).build()
            assertEquals(42L, db.entries().get("first", "selection:")!!.savedAt)
            db.entries().deletePrefix("first", "selection:")
            assertNull(db.entries().get("first", "selection:next"))
            assertEquals("[1]", db.entries().get("second", "selection:")!!.json)
            db.entries().clear("second")
            assertNull(db.entries().get("second", "selection:"))
        } finally { db.close(); context.deleteDatabase(name) }
    }
}
