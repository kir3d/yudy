package app.yudy.data.cache

import androidx.room.*

@Entity(tableName = "cached_entries", primaryKeys = ["owner", "key"])
data class CacheEntry(val owner: String, val key: String, val json: String, val savedAt: Long)
@Dao
interface CacheDao {
    @Query("SELECT * FROM cached_entries WHERE owner = :owner AND `key` = :key") suspend fun get(owner: String, key: String): CacheEntry?
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun put(entry: CacheEntry)
    @Query("DELETE FROM cached_entries WHERE owner = :owner AND `key` = :key") suspend fun delete(owner: String, key: String)
    @Query("DELETE FROM cached_entries WHERE owner = :owner AND substr(`key`, 1, length(:prefix)) = :prefix") suspend fun deletePrefix(owner: String, prefix: String)
    @Query("DELETE FROM cached_entries WHERE owner = :owner") suspend fun clear(owner: String)
}
@Database(entities = [CacheEntry::class], version = 1, exportSchema = true)
abstract class CacheDatabase: RoomDatabase() { abstract fun entries(): CacheDao }
