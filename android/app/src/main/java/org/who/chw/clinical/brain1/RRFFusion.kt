package org.who.chw.clinical.brain1

import org.who.chw.clinical.data.ChunkResult

/**
 * Reciprocal Rank Fusion (RRF) for combining search results from multiple sources.
 *
 * RRF is a simple, effective method for fusing ranked lists:
 * - No training required
 * - Works well with different scoring scales
 * - Proven effective in information retrieval
 *
 * Formula: RRF(d) = Σ 1 / (k + rank(d))
 * Where k is a constant (typically 60) and rank starts at 1.
 */
object RRFFusion {

    /**
     * RRF constant - controls how quickly rank influence diminishes.
     * Higher values give more weight to lower-ranked results.
     * Standard value is 60, but can be tuned for specific use cases.
     */
    private const val RRF_K = 60

    /**
     * Fuse results from vector and keyword search using RRF.
     *
     * @param vectorResults Results from vector similarity search
     * @param keywordResults Results from BM25 keyword search
     * @param finalCount Number of final results to return
     * @return Fused results ordered by combined RRF score
     */
    fun fuse(
        vectorResults: List<ChunkResult>,
        keywordResults: List<ChunkResult>,
        finalCount: Int = 10
    ): List<ChunkResult> {
        // Map to store RRF scores by chunk ID
        val rrfScores = mutableMapOf<String, Double>()
        // Map to store original ChunkResult for each chunk ID
        val chunkMap = mutableMapOf<String, ChunkResult>()

        // Score contributions from vector search (rank starts at 1)
        vectorResults.forEachIndexed { index, result ->
            val rank = index + 1
            val score = 1.0 / (RRF_K + rank)
            rrfScores[result.chunkId] = (rrfScores[result.chunkId] ?: 0.0) + score
            // Store the result (prefer vector result if duplicate)
            chunkMap.putIfAbsent(result.chunkId, result)
        }

        // Score contributions from keyword search (rank starts at 1)
        keywordResults.forEachIndexed { index, result ->
            val rank = index + 1
            val score = 1.0 / (RRF_K + rank)
            rrfScores[result.chunkId] = (rrfScores[result.chunkId] ?: 0.0) + score
            // Store the result if not already present
            chunkMap.putIfAbsent(result.chunkId, result)
        }

        // Sort by RRF score and take top results
        return rrfScores.entries
            .sortedByDescending { it.value }
            .take(finalCount)
            .mapNotNull { (chunkId, rrfScore) ->
                chunkMap[chunkId]?.copy(
                    // Replace similarity with normalized RRF score
                    similarity = rrfScore.toFloat()
                )
            }
    }

    /**
     * Alternative fusion with configurable weights.
     *
     * Allows weighting vector vs keyword results differently.
     *
     * @param vectorResults Results from vector similarity search
     * @param keywordResults Results from BM25 keyword search
     * @param vectorWeight Weight for vector results (default 1.0)
     * @param keywordWeight Weight for keyword results (default 1.0)
     * @param finalCount Number of final results to return
     * @return Fused results ordered by weighted RRF score
     */
    fun fuseWeighted(
        vectorResults: List<ChunkResult>,
        keywordResults: List<ChunkResult>,
        vectorWeight: Double = 1.0,
        keywordWeight: Double = 1.0,
        finalCount: Int = 10
    ): List<ChunkResult> {
        val rrfScores = mutableMapOf<String, Double>()
        val chunkMap = mutableMapOf<String, ChunkResult>()

        // Weighted vector scores
        vectorResults.forEachIndexed { index, result ->
            val rank = index + 1
            val score = vectorWeight / (RRF_K + rank)
            rrfScores[result.chunkId] = (rrfScores[result.chunkId] ?: 0.0) + score
            chunkMap.putIfAbsent(result.chunkId, result)
        }

        // Weighted keyword scores
        keywordResults.forEachIndexed { index, result ->
            val rank = index + 1
            val score = keywordWeight / (RRF_K + rank)
            rrfScores[result.chunkId] = (rrfScores[result.chunkId] ?: 0.0) + score
            chunkMap.putIfAbsent(result.chunkId, result)
        }

        return rrfScores.entries
            .sortedByDescending { it.value }
            .take(finalCount)
            .mapNotNull { (chunkId, rrfScore) ->
                chunkMap[chunkId]?.copy(similarity = rrfScore.toFloat())
            }
    }
}
