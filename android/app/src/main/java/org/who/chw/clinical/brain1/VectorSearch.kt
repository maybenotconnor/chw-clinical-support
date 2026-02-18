package org.who.chw.clinical.brain1

import org.who.chw.clinical.data.ChunkRepository
import org.who.chw.clinical.data.ChunkResult

/**
 * Wrapper for sqlite-vec vector similarity search.
 */
class VectorSearch(private val chunkRepository: ChunkRepository) {

    /**
     * Search for similar chunks using vector similarity.
     *
     * @param queryEmbedding 384-dimensional query embedding
     * @param topK Number of results to return
     * @return List of search results ordered by similarity
     */
    suspend fun search(
        queryEmbedding: FloatArray,
        topK: Int = 10
    ): List<SearchResult> {
        val chunks = chunkRepository.searchByVector(queryEmbedding, topK)

        return chunks.map { chunk ->
            SearchResult(
                chunkId = chunk.chunkId,
                content = chunk.content,
                pageNumber = chunk.pageNumber,
                score = chunk.similarity,
                headings = chunk.headings
            )
        }
    }
}
