package org.who.chw.clinical.brain1

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.nio.LongBuffer
import kotlin.math.sqrt

/**
 * On-device embedding engine using ONNX Runtime.
 *
 * Generates 384-dimensional embeddings using a quantized MiniLM-L6-v2 model
 * with proper WordPiece tokenization.
 */
class EmbeddingEngine(private val context: Context) {

    companion object {
        private const val TAG = "EmbeddingEngine"
        private const val MODEL_PATH = "models/minilm-l6-v2-quantized.onnx"
        private const val MAX_SEQ_LENGTH = 256
        const val EMBEDDING_DIM = 384
    }

    private var ortEnvironment: OrtEnvironment? = null
    private var ortSession: OrtSession? = null
    private lateinit var tokenizer: WordPieceTokenizer
    private var isInitialized = false

    /**
     * Initialize the ONNX model.
     *
     * Must be called before using embed().
     */
    suspend fun initialize() = withContext(Dispatchers.IO) {
        if (isInitialized) return@withContext

        Log.d(TAG, "Initializing embedding engine...")

        try {
            ortEnvironment = OrtEnvironment.getEnvironment()

            // Load WordPiece tokenizer
            tokenizer = WordPieceTokenizer(context)

            // Load model from assets
            val modelBytes = context.assets.open(MODEL_PATH).use { it.readBytes() }

            // Configure session options
            val sessionOptions = OrtSession.SessionOptions().apply {
                setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
                setIntraOpNumThreads(4)
            }

            ortSession = ortEnvironment!!.createSession(modelBytes, sessionOptions)

            isInitialized = true
            Log.d(TAG, "Embedding engine initialized successfully")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize embedding engine", e)
            throw RuntimeException("Failed to load ONNX model", e)
        }
    }

    /**
     * Generate embedding for input text.
     *
     * @param text Input text to embed
     * @return 384-dimensional normalized embedding
     */
    suspend fun embed(text: String): FloatArray = withContext(Dispatchers.Default) {
        require(isInitialized) { "EmbeddingEngine not initialized. Call initialize() first." }

        val tokens = tokenize(text)

        // Create input tensors
        val inputIds = createLongTensor(tokens.inputIds)
        val attentionMask = createLongTensor(tokens.attentionMask)
        val tokenTypeIds = createLongTensor(tokens.tokenTypeIds)

        try {
            // Run inference
            val inputs = mapOf(
                "input_ids" to inputIds,
                "attention_mask" to attentionMask,
                "token_type_ids" to tokenTypeIds
            )

            val results = ortSession!!.run(inputs)

            // Extract embeddings from output
            val outputTensor = results[0]
            val output = outputTensor.value as Array<Array<FloatArray>>

            // Mean pooling over sequence length (with attention mask)
            val embedding = meanPool(output[0], tokens.attentionMask)

            // L2 normalize for cosine similarity
            normalize(embedding)

            embedding
        } finally {
            inputIds.close()
            attentionMask.close()
            tokenTypeIds.close()
        }
    }

    /**
     * Tokenize input text using WordPiece tokenizer.
     */
    private fun tokenize(text: String): TokenizedInput {
        val result = tokenizer.tokenize(text, MAX_SEQ_LENGTH)
        return TokenizedInput(
            inputIds = result.inputIds,
            attentionMask = result.attentionMask,
            tokenTypeIds = result.tokenTypeIds
        )
    }

    private fun createLongTensor(data: LongArray): OnnxTensor {
        val buffer = LongBuffer.wrap(data)
        return OnnxTensor.createTensor(
            ortEnvironment,
            buffer,
            longArrayOf(1, data.size.toLong())
        )
    }

    /**
     * Mean pooling over sequence positions with attention mask.
     */
    private fun meanPool(hiddenStates: Array<FloatArray>, attentionMask: LongArray): FloatArray {
        val embedding = FloatArray(EMBEDDING_DIM)
        var count = 0

        for (i in hiddenStates.indices) {
            if (attentionMask[i] == 1L) {
                for (j in 0 until EMBEDDING_DIM) {
                    embedding[j] += hiddenStates[i][j]
                }
                count++
            }
        }

        if (count > 0) {
            for (j in 0 until EMBEDDING_DIM) {
                embedding[j] /= count
            }
        }

        return embedding
    }

    /**
     * L2 normalize embedding for cosine similarity.
     */
    private fun normalize(embedding: FloatArray) {
        var norm = 0f
        for (value in embedding) {
            norm += value * value
        }
        norm = sqrt(norm)

        if (norm > 0) {
            for (i in embedding.indices) {
                embedding[i] /= norm
            }
        }
    }

    /**
     * Release resources.
     */
    fun close() {
        ortSession?.close()
        ortEnvironment?.close()
        isInitialized = false
    }

    private data class TokenizedInput(
        val inputIds: LongArray,
        val attentionMask: LongArray,
        val tokenTypeIds: LongArray
    )
}
