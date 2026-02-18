package org.who.chw.clinical.data

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Chunk categories - matches extraction pipeline
 */
object ChunkCategory {
    const val CONTENT = "content"    // Clinical guidelines, treatments, symptoms
    const val METADATA = "metadata"  // TOC, abbreviations, foreword, credits
}

/**
 * Data class representing a search result chunk.
 */
data class ChunkResult(
    val chunkId: String,
    val docId: String,
    val content: String,
    val pageNumber: Int?,
    val similarity: Float,
    val headings: List<String> = emptyList(),
    val category: String = ChunkCategory.CONTENT
)

/**
 * Repository for accessing chunks from the clinical guidelines database.
 */
class ChunkRepository(private val dbHelper: DatabaseHelper) {

    companion object {
        private const val TAG = "ChunkRepository"
        private const val EMBEDDING_DIM = 384
        // Minimum content length to filter out tiny fragments (table cells, headers, etc.)
        private const val MIN_CONTENT_LENGTH = 50
    }

    /**
     * Search for chunks similar to the query embedding.
     *
     * Uses sqlite-vec for vector similarity search.
     * Filters out small chunks (< MIN_CONTENT_LENGTH) that lack context.
     * Filters out metadata chunks (TOC, abbreviations, etc.) by default.
     *
     * @param queryEmbedding 384-dimensional embedding vector
     * @param topK Number of results to return
     * @param contentOnly If true, exclude metadata chunks (TOC, abbreviations, etc.)
     * @return List of matching chunks ordered by similarity
     */
    suspend fun searchByVector(
        queryEmbedding: FloatArray,
        topK: Int = 10,
        contentOnly: Boolean = true
    ): List<ChunkResult> = withContext(Dispatchers.IO) {

        val db = dbHelper.getDatabase()

        // Convert embedding to JSON format for sqlite-vec
        val embeddingJson = floatArrayToJson(queryEmbedding)

        Log.d(TAG, "Searching with embedding (first 5 values): ${queryEmbedding.take(5)}")

        // Fetch extra results to compensate for filtering small chunks and metadata
        val fetchK = if (contentOnly) topK * 4 else topK * 3

        // Vector similarity search using sqlite-vec
        // The MATCH operator performs KNN search
        // Note: sqlite-vec doesn't support WHERE clauses in MATCH, so we filter in Kotlin
        val query = """
            SELECT
                e.chunk_id,
                e.distance,
                c.doc_id,
                c.content,
                c.page_number,
                c.category,
                m.headings_json
            FROM embeddings e
            INNER JOIN chunks c ON c.chunk_id = e.chunk_id
            LEFT JOIN chunk_metadata m ON c.chunk_id = m.chunk_id
            WHERE e.embedding MATCH ?
                AND k = ?
            ORDER BY e.distance
        """

        try {
            val cursor = db.rawQuery(query, arrayOf(embeddingJson, fetchK.toString()))

            buildList {
                cursor.use {
                    while (it.moveToNext()) {
                        val chunkId = it.getString(0)
                        val distance = it.getFloat(1)
                        val docId = it.getString(2)
                        val content = it.getString(3)
                        val pageNumber = if (it.isNull(4)) null else it.getInt(4)
                        val category = it.getString(5) ?: ChunkCategory.CONTENT
                        val headingsJson = it.getString(6)

                        // Skip chunks that are too small to be meaningful
                        if (content.length < MIN_CONTENT_LENGTH) continue

                        // Skip metadata chunks (TOC, abbreviations, etc.) if contentOnly
                        if (contentOnly && category == ChunkCategory.METADATA) continue

                        // Parse headings from JSON
                        val headings = parseHeadingsJson(headingsJson)

                        // Convert distance to similarity score (1 - distance for cosine)
                        val similarity = 1.0f - distance

                        add(
                            ChunkResult(
                                chunkId = chunkId,
                                docId = docId,
                                content = content,
                                pageNumber = pageNumber,
                                similarity = similarity,
                                headings = headings,
                                category = category
                            )
                        )
                    }
                }
            }
            .take(topK)  // Limit to requested count after filtering
            .also {
                Log.d(TAG, "Found ${it.size} results (after filtering small/metadata chunks)")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Vector search failed", e)
            // Fallback to empty results if sqlite-vec not available
            emptyList()
        }
    }

    /**
     * Search for chunks by keyword using FTS5 full-text search.
     *
     * Uses BM25 ranking for relevance scoring.
     * Filters out small chunks (< MIN_CONTENT_LENGTH) that lack context.
     * Filters out metadata chunks (TOC, abbreviations, etc.) by default.
     *
     * @param query Search query text
     * @param topK Number of results to return
     * @param contentOnly If true, exclude metadata chunks (TOC, abbreviations, etc.)
     * @return List of matching chunks ordered by BM25 relevance
     */
    suspend fun searchByKeyword(
        query: String,
        topK: Int = 10,
        contentOnly: Boolean = true
    ): List<ChunkResult> = withContext(Dispatchers.IO) {
        val db = dbHelper.getDatabase()

        // Split query into terms and format for FTS5
        val terms = query.trim().split("\\s+".toRegex()).filter { it.isNotBlank() }
        if (terms.isEmpty()) return@withContext emptyList()

        // Join terms with OR for broader matching
        val ftsQuery = terms.joinToString(" OR ") { "\"$it\"" }

        Log.d(TAG, "Keyword search with FTS query: $ftsQuery, contentOnly: $contentOnly")

        // Fetch extra to compensate for filtering
        val fetchK = topK * 3

        // FTS5 supports WHERE clauses, so we can filter category in SQL
        val sql = if (contentOnly) {
            """
            SELECT
                c.chunk_id,
                c.doc_id,
                c.content,
                c.page_number,
                c.category,
                m.headings_json,
                bm25(chunks_fts) as bm25_score
            FROM chunks_fts fts
            JOIN chunks c ON fts.chunk_id = c.chunk_id
            LEFT JOIN chunk_metadata m ON c.chunk_id = m.chunk_id
            WHERE chunks_fts MATCH ?
                AND c.category = '${ChunkCategory.CONTENT}'
            ORDER BY bm25(chunks_fts)
            LIMIT ?
            """
        } else {
            """
            SELECT
                c.chunk_id,
                c.doc_id,
                c.content,
                c.page_number,
                c.category,
                m.headings_json,
                bm25(chunks_fts) as bm25_score
            FROM chunks_fts fts
            JOIN chunks c ON fts.chunk_id = c.chunk_id
            LEFT JOIN chunk_metadata m ON c.chunk_id = m.chunk_id
            WHERE chunks_fts MATCH ?
            ORDER BY bm25(chunks_fts)
            LIMIT ?
            """
        }

        try {
            val cursor = db.rawQuery(sql, arrayOf(ftsQuery, fetchK.toString()))

            buildList {
                cursor.use {
                    while (it.moveToNext()) {
                        val chunkId = it.getString(0)
                        val docId = it.getString(1)
                        val content = it.getString(2)
                        val pageNumber = if (it.isNull(3)) null else it.getInt(3)
                        val category = it.getString(4) ?: ChunkCategory.CONTENT
                        val headingsJson = it.getString(5)
                        val bm25Score = it.getFloat(6)

                        // Skip chunks that are too small to be meaningful
                        if (content.length < MIN_CONTENT_LENGTH) continue

                        // Parse headings from JSON
                        val headings = parseHeadingsJson(headingsJson)

                        // BM25 returns negative scores (more negative = better match)
                        // Convert to positive similarity score
                        val similarity = kotlin.math.abs(bm25Score)

                        add(
                            ChunkResult(
                                chunkId = chunkId,
                                docId = docId,
                                content = content,
                                pageNumber = pageNumber,
                                similarity = similarity,
                                headings = headings,
                                category = category
                            )
                        )
                    }
                }
            }
            .take(topK)  // Limit to requested count after filtering
            .also {
                Log.d(TAG, "Keyword search found ${it.size} results (after filtering)")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Keyword search failed", e)
            emptyList()
        }
    }

    /**
     * Get all chunks from the same section (same top-level heading).
     * Used to expand a search result with full section context.
     *
     * @param headings The heading hierarchy of the matched chunk
     * @param pageNumber The page number to help narrow down the section
     * @return Concatenated content from all chunks in the section
     */
    suspend fun getSectionContent(
        headings: List<String>,
        pageNumber: Int?
    ): String = withContext(Dispatchers.IO) {
        if (headings.isEmpty()) return@withContext ""

        val db = dbHelper.getDatabase()

        // Use the top-level heading to find related chunks
        val topHeading = headings.firstOrNull() ?: return@withContext ""

        // Find all chunks with the same top heading, within a page range
        val pageStart = (pageNumber ?: 1) - 2
        val pageEnd = (pageNumber ?: 1) + 5

        val query = """
            SELECT c.content, c.page_number, m.headings_json
            FROM chunks c
            JOIN chunk_metadata m ON c.chunk_id = m.chunk_id
            WHERE m.headings_json LIKE ?
            AND c.page_number BETWEEN ? AND ?
            AND length(c.content) > 30
            ORDER BY c.page_number, c.chunk_id
            LIMIT 20
        """

        try {
            val cursor = db.rawQuery(
                query,
                arrayOf("%\"$topHeading\"%", pageStart.toString(), pageEnd.toString())
            )

            val contentParts = mutableListOf<String>()
            cursor.use {
                while (it.moveToNext()) {
                    val content = it.getString(0)
                    // Clean up extraction artifacts
                    val cleaned = content
                        .replace(Regex(", 1 = "), ": ")
                        .replace(Regex("\\s+"), " ")
                        .trim()
                    if (cleaned.length > 30) {
                        contentParts.add(cleaned)
                    }
                }
            }

            // Deduplicate and join
            contentParts.distinct().joinToString("\n\n")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get section content", e)
            ""
        }
    }

    /**
     * Get a specific chunk by ID.
     */
    suspend fun getChunk(chunkId: String): ChunkResult? = withContext(Dispatchers.IO) {
        val db = dbHelper.getDatabase()

        val query = """
            SELECT
                c.chunk_id,
                c.doc_id,
                c.content,
                c.page_number,
                m.headings_json
            FROM chunks c
            LEFT JOIN chunk_metadata m ON c.chunk_id = m.chunk_id
            WHERE c.chunk_id = ?
        """

        val cursor = db.rawQuery(query, arrayOf(chunkId))

        cursor.use {
            if (it.moveToFirst()) {
                ChunkResult(
                    chunkId = it.getString(0),
                    docId = it.getString(1),
                    content = it.getString(2),
                    pageNumber = if (it.isNull(3)) null else it.getInt(3),
                    similarity = 1.0f, // Direct lookup, no similarity score
                    headings = parseHeadingsJson(it.getString(4))
                )
            } else {
                null
            }
        }
    }

    /**
     * Get total number of chunks in the database.
     */
    suspend fun getChunkCount(): Int = withContext(Dispatchers.IO) {
        val db = dbHelper.getDatabase()
        val cursor = db.rawQuery("SELECT COUNT(*) FROM chunks", null)

        cursor.use {
            if (it.moveToFirst()) it.getInt(0) else 0
        }
    }

    /**
     * Convert float array to JSON string for sqlite-vec.
     */
    private fun floatArrayToJson(floats: FloatArray): String {
        return floats.joinToString(",", "[", "]")
    }

    /**
     * Pack float array to binary format for sqlite-vec (alternative method).
     */
    @Suppress("unused")
    private fun packFloatArray(floats: FloatArray): ByteArray {
        val buffer = ByteBuffer.allocate(floats.size * 4)
        buffer.order(ByteOrder.LITTLE_ENDIAN)
        floats.forEach { buffer.putFloat(it) }
        return buffer.array()
    }

    /**
     * Parse headings JSON array to list.
     */
    private fun parseHeadingsJson(json: String?): List<String> {
        if (json.isNullOrBlank()) return emptyList()

        return try {
            val array = JSONArray(json)
            buildList {
                for (i in 0 until array.length()) {
                    add(array.getString(i))
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to parse headings JSON: $json", e)
            emptyList()
        }
    }
}
