package org.who.chw.clinical.brain1

import android.util.Log
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import org.who.chw.clinical.data.ChunkRepository
import org.who.chw.clinical.data.ChunkResult

/**
 * Search result for display.
 *
 * @param chunkId Unique identifier of the matched chunk
 * @param content The matched chunk content (snippet)
 * @param expandedContent Full section content for context (may be null if not expanded)
 * @param pageNumber Page number in the source document
 * @param score Relevance score
 * @param headings Heading hierarchy (section path)
 */
data class SearchResult(
    val chunkId: String,
    val content: String,
    val expandedContent: String? = null,
    val pageNumber: Int?,
    val score: Float,
    val headings: List<String>
)

/**
 * Search state for UI.
 */
sealed class SearchState {
    data object Idle : SearchState()
    data object Loading : SearchState()
    data class Success(val results: List<SearchResult>) : SearchState()
    data class Error(val message: String) : SearchState()
}

/**
 * Search mode configuration.
 */
enum class SearchMode {
    VECTOR_ONLY,     // Only vector similarity search
    KEYWORD_ONLY,    // Only BM25 keyword search
    HYBRID           // Combined vector + keyword with RRF fusion
}

/**
 * Brain 1 search service orchestrating embedding and vector search.
 *
 * Phase 2 adds hybrid search combining vector and keyword (BM25) search
 * with Reciprocal Rank Fusion (RRF) for improved relevance.
 */
class SearchService(
    private val embeddingEngine: EmbeddingEngine,
    private val chunkRepository: ChunkRepository
) {
    companion object {
        private const val TAG = "SearchService"
        private const val DEFAULT_TOP_K = 10
        private const val VECTOR_TOP_K = 15  // Fetch more for fusion
        private const val KEYWORD_TOP_K = 15
    }

    /**
     * Current search mode - default to hybrid for Phase 2.
     */
    var searchMode: SearchMode = SearchMode.HYBRID

    /**
     * Initialize the search service.
     */
    suspend fun initialize() {
        Log.d(TAG, "Initializing search service...")
        embeddingEngine.initialize()
        Log.d(TAG, "Search service ready")
    }

    /**
     * Search for clinical guidelines matching the query.
     *
     * Uses hybrid search (vector + keyword) with RRF fusion for Phase 2.
     *
     * @param query Search query text
     * @param topK Number of results to return
     * @return SearchState with results or error
     */
    suspend fun search(query: String, topK: Int = DEFAULT_TOP_K): SearchState {
        // Validate input
        if (query.isBlank()) {
            return SearchState.Error("Please enter a search query")
        }

        return try {
            Log.d(TAG, "Searching for: $query (mode: $searchMode)")
            val startTime = System.currentTimeMillis()

            val chunks: List<ChunkResult> = when (searchMode) {
                SearchMode.VECTOR_ONLY -> searchVectorOnly(query, topK)
                SearchMode.KEYWORD_ONLY -> searchKeywordOnly(query, topK)
                SearchMode.HYBRID -> searchHybrid(query, topK)
            }

            val totalTime = System.currentTimeMillis() - startTime
            Log.d(TAG, "Total search time: ${totalTime}ms")

            // Convert to search results with expanded section content
            if (chunks.isEmpty()) {
                SearchState.Error("No matching guidelines found. Try different keywords.")
            } else {
                // Expand each result with full section context
                val results = chunks.map { chunk ->
                    val expandedContent = if (chunk.headings.isNotEmpty()) {
                        chunkRepository.getSectionContent(chunk.headings, chunk.pageNumber)
                    } else {
                        null
                    }

                    SearchResult(
                        chunkId = chunk.chunkId,
                        content = chunk.content,
                        expandedContent = expandedContent?.takeIf { it.length > chunk.content.length },
                        pageNumber = chunk.pageNumber,
                        score = chunk.similarity,
                        headings = chunk.headings
                    )
                }
                Log.d(TAG, "Expanded ${results.count { it.expandedContent != null }} results with section context")
                SearchState.Success(results)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Search failed", e)
            SearchState.Error("Search error: ${e.localizedMessage ?: "Unknown error"}")
        }
    }

    /**
     * Vector-only search using semantic embeddings.
     */
    private suspend fun searchVectorOnly(query: String, topK: Int): List<ChunkResult> {
        val startTime = System.currentTimeMillis()

        val embedding = embeddingEngine.embed(query)
        Log.d(TAG, "Embedding generated in ${System.currentTimeMillis() - startTime}ms")

        val searchStart = System.currentTimeMillis()
        val results = chunkRepository.searchByVector(embedding, topK)
        Log.d(TAG, "Vector search completed in ${System.currentTimeMillis() - searchStart}ms")

        return results
    }

    /**
     * Keyword-only search using BM25.
     */
    private suspend fun searchKeywordOnly(query: String, topK: Int): List<ChunkResult> {
        val startTime = System.currentTimeMillis()
        val results = chunkRepository.searchByKeyword(query, topK)
        Log.d(TAG, "Keyword search completed in ${System.currentTimeMillis() - startTime}ms")
        return results
    }

    /**
     * Hybrid search combining vector and keyword search with RRF fusion.
     *
     * Runs both searches in parallel for performance, then fuses results.
     */
    private suspend fun searchHybrid(query: String, topK: Int): List<ChunkResult> = coroutineScope {
        val startTime = System.currentTimeMillis()

        // Generate embedding (needed for vector search)
        val embedding = embeddingEngine.embed(query)
        val embeddingTime = System.currentTimeMillis() - startTime
        Log.d(TAG, "Embedding generated in ${embeddingTime}ms")

        // Run vector and keyword search in parallel
        val vectorDeferred = async {
            val start = System.currentTimeMillis()
            chunkRepository.searchByVector(embedding, VECTOR_TOP_K).also {
                Log.d(TAG, "Vector search: ${it.size} results in ${System.currentTimeMillis() - start}ms")
            }
        }

        val keywordDeferred = async {
            val start = System.currentTimeMillis()
            chunkRepository.searchByKeyword(query, KEYWORD_TOP_K).also {
                Log.d(TAG, "Keyword search: ${it.size} results in ${System.currentTimeMillis() - start}ms")
            }
        }

        val vectorResults = vectorDeferred.await()
        val keywordResults = keywordDeferred.await()

        // Fuse results using RRF
        val fusionStart = System.currentTimeMillis()
        val fusedResults = RRFFusion.fuse(vectorResults, keywordResults, topK)
        Log.d(TAG, "RRF fusion: ${fusedResults.size} results in ${System.currentTimeMillis() - fusionStart}ms")

        fusedResults
    }

    /**
     * Release resources.
     */
    fun close() {
        embeddingEngine.close()
    }
}
