package org.who.chw.clinical.data

import android.content.Context
import android.util.Log
import io.requery.android.database.sqlite.SQLiteCustomExtension
import io.requery.android.database.sqlite.SQLiteDatabase
import io.requery.android.database.sqlite.SQLiteDatabaseConfiguration
import java.io.File
import java.io.FileOutputStream

/**
 * Database helper for loading SQLite with sqlite-vec extension.
 *
 * Uses requery/sqlite-android to enable extension loading, which is
 * blocked in Android's built-in SQLite.
 */
class DatabaseHelper(private val context: Context) {

    companion object {
        private const val TAG = "DatabaseHelper"
        private const val DATABASE_NAME = "guidelines.db"
        private const val SQLITE_VEC_EXTENSION = "libvec0.so"
    }

    @Volatile
    private var database: SQLiteDatabase? = null

    /**
     * Get the database instance, initializing if necessary.
     *
     * Thread-safe lazy initialization with sqlite-vec extension loaded.
     */
    fun getDatabase(): SQLiteDatabase {
        return database ?: synchronized(this) {
            database ?: openDatabase().also { database = it }
        }
    }

    private fun openDatabase(): SQLiteDatabase {
        // Copy database from assets if it doesn't exist
        val dbPath = copyDatabaseFromAssets()

        // Get path to sqlite-vec extension
        val extensionPath = "${context.applicationInfo.nativeLibraryDir}/$SQLITE_VEC_EXTENSION"

        Log.d(TAG, "Opening database at: $dbPath")
        Log.d(TAG, "Loading sqlite-vec from: $extensionPath")

        // Verify extension exists
        val extensionFile = File(extensionPath)
        if (!extensionFile.exists()) {
            Log.w(TAG, "sqlite-vec extension not found at $extensionPath")
            // Continue anyway - will fail gracefully if vector search is used
        }

        // Create sqlite-vec extension configuration
        val vecExtension = SQLiteCustomExtension(extensionPath, "sqlite3_vec_init")

        // Configure database with extension
        val config = SQLiteDatabaseConfiguration(
            dbPath,
            SQLiteDatabase.OPEN_READONLY,
            emptyList(), // No custom functions
            emptyList(), // No custom collators
            listOf(vecExtension) // Load sqlite-vec
        )

        return try {
            SQLiteDatabase.openDatabase(config, null, null).also {
                // Verify sqlite-vec is loaded
                verifyVecExtension(it)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to open database with sqlite-vec", e)
            // Fallback: open without extension (vector search won't work)
            val fallbackConfig = SQLiteDatabaseConfiguration(
                dbPath,
                SQLiteDatabase.OPEN_READONLY
            )
            SQLiteDatabase.openDatabase(fallbackConfig, null, null)
        }
    }

    private fun copyDatabaseFromAssets(): String {
        val dbFile = context.getDatabasePath(DATABASE_NAME)

        // Create parent directories if needed
        dbFile.parentFile?.mkdirs()

        if (!dbFile.exists()) {
            Log.d(TAG, "Copying database from assets to: ${dbFile.absolutePath}")

            try {
                context.assets.open("databases/$DATABASE_NAME").use { input ->
                    FileOutputStream(dbFile).use { output ->
                        input.copyTo(output)
                    }
                }
                Log.d(TAG, "Database copied successfully")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to copy database from assets", e)
                throw RuntimeException("Failed to initialize database", e)
            }
        } else {
            Log.d(TAG, "Database already exists at: ${dbFile.absolutePath}")
        }

        return dbFile.absolutePath
    }

    private fun verifyVecExtension(db: SQLiteDatabase) {
        try {
            val cursor = db.rawQuery("SELECT vec_version()", null)
            cursor.use {
                if (it.moveToFirst()) {
                    val version = it.getString(0)
                    Log.d(TAG, "sqlite-vec version: $version")
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "sqlite-vec extension not available: ${e.message}")
        }
    }

    /**
     * Close the database connection.
     */
    fun close() {
        database?.close()
        database = null
    }
}
