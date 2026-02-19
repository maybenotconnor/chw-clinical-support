package org.who.chw.clinical.brain2

import android.content.Context
import android.util.Log
import com.llamatik.library.platform.GenStream
import com.llamatik.library.platform.LlamaBridge
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import android.app.ActivityManager
import java.io.File

/**
 * MedGemma inference engine for Brain 2 synthesis.
 *
 * Runs MedGemma 4B-it on-device via Llamatik (llama.cpp wrapper).
 * The GGUF model is split into 500MB chunks in APK assets (to stay under
 * Java's 2GB array limit during APK packaging) and reassembled to cache
 * on first run.
 *
 * Follows the same lifecycle pattern as [EmbeddingEngine]:
 * initialize() -> generate() -> close()
 */
class MedGemmaEngine {

    companion object {
        private const val TAG = "MedGemmaEngine"
        private const val MODEL_CHUNKS_DIR = "models/medgemma-chunks"
        private const val MODEL_CACHE_NAME = "medgemma-4b-it-Q4_K_M.gguf"
    }

    private var isInitialized = false
    private var isAvailable = false

    /**
     * Current engine state.
     */
    sealed class State {
        data object NotInitialized : State()
        data object Initializing : State()
        data object Ready : State()
        data object Generating : State()
        data class Error(val message: String) : State()
    }

    var state: State = State.NotInitialized
        private set

    /**
     * Initialize the engine by reassembling the GGUF model from asset chunks
     * and loading it via Llamatik.
     *
     * On first run, the 500MB chunks are concatenated into a single file in
     * the cache directory (~10-30s). Subsequent launches skip this step.
     *
     * @param context Android application context for asset access and cache dir
     */
    suspend fun initialize(context: Context) = withContext(Dispatchers.IO) {
        if (isInitialized && isAvailable) return@withContext

        state = State.Initializing
        Log.d(TAG, "Initializing MedGemma engine (on-device via llama.cpp)")

        // Log available device memory
        try {
            val activityManager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val memInfo = ActivityManager.MemoryInfo()
            activityManager.getMemoryInfo(memInfo)
            Log.d(TAG, "Device memory — available: ${memInfo.availMem / (1024 * 1024)}MB, " +
                    "total: ${memInfo.totalMem / (1024 * 1024)}MB, lowMemory: ${memInfo.lowMemory}")
        } catch (e: Exception) {
            Log.w(TAG, "Could not read memory info: ${e.message}")
        }

        try {
            // Reassemble model chunks from assets to cache dir if not already present.
            // The GGUF is split into 500MB chunks in assets/ to stay under Java's
            // 2GB array size limit during APK packaging.
            val cacheFile = File(context.cacheDir, MODEL_CACHE_NAME)
            if (!cacheFile.exists()) {
                Log.d(TAG, "Reassembling model from asset chunks (~2.5GB, this may take a moment)...")
                val chunkList = context.assets.list(MODEL_CHUNKS_DIR)
                val chunks = chunkList?.sorted()
                    ?: throw IllegalStateException("No model chunks found in assets/$MODEL_CHUNKS_DIR")
                Log.d(TAG, "Found ${chunks.size} chunks: $chunks")

                cacheFile.outputStream().use { output ->
                    for (chunk in chunks) {
                        Log.d(TAG, "  Copying chunk: $chunk")
                        context.assets.open("$MODEL_CHUNKS_DIR/$chunk").use { input ->
                            input.copyTo(output, bufferSize = 8 * 1024 * 1024)
                        }
                    }
                }
                val fileSizeMB = cacheFile.length() / (1024 * 1024)
                Log.d(TAG, "Model reassembly complete: ${fileSizeMB}MB")

                // Validate reassembled file — GGUF should be >2GB
                if (cacheFile.length() < 2_000_000_000L) {
                    val msg = "Reassembled GGUF too small (${fileSizeMB}MB). Expected >2GB. " +
                            "Asset chunks may be incomplete."
                    cacheFile.delete()
                    throw IllegalStateException(msg)
                }
            } else {
                Log.d(TAG, "Model already cached: ${cacheFile.length() / (1024 * 1024)}MB")
            }

            // Load model via Llamatik
            Log.d(TAG, "Loading model via LlamaBridge from: ${cacheFile.absolutePath}")
            val success = LlamaBridge.initGenerateModel(cacheFile.absolutePath)
            Log.d(TAG, "LlamaBridge.initGenerateModel returned: $success")

            if (success) {
                isAvailable = true
                isInitialized = true
                state = State.Ready
                Log.d(TAG, "MedGemma engine ready (on-device)")
            } else {
                isInitialized = true
                isAvailable = false
                state = State.Error("Failed to load model via llama.cpp — device may lack sufficient RAM")
                Log.e(TAG, "LlamaBridge.initGenerateModel returned false")
            }
        } catch (e: Exception) {
            state = State.Error("Model init failed: ${e.localizedMessage}")
            isInitialized = true
            isAvailable = false
            Log.e(TAG, "MedGemma init failed", e)
        }
    }

    /**
     * Check if the engine is ready to generate.
     */
    fun isReady(): Boolean = isAvailable && state is State.Ready

    /**
     * Generate a completion (non-streaming).
     *
     * @param prompt Full prompt text (should include Gemma chat template tags)
     * @param maxTokens Unused — Llamatik uses llama.cpp defaults
     * @param temperature Unused — Llamatik uses llama.cpp defaults
     * @return Generated text
     */
    suspend fun generate(
        prompt: String,
        maxTokens: Int = 512,
        temperature: Float = 0.3f
    ): String = withContext(Dispatchers.IO) {
        require(isReady()) { "MedGemmaEngine not ready. Call initialize() first." }

        state = State.Generating
        Log.d(TAG, "Generating on-device (prompt: ${prompt.length} chars)")

        try {
            val result = LlamaBridge.generate(prompt)
            state = State.Ready
            Log.d(TAG, "Generation complete (${result.length} chars)")
            result
        } catch (e: Exception) {
            state = State.Ready
            Log.e(TAG, "Generation failed", e)
            throw RuntimeException("MedGemma generation failed: ${e.message}", e)
        }
    }

    /**
     * Generate a completion with streaming token output.
     *
     * Returns a Flow that emits tokens as they're generated.
     *
     * @param prompt Full prompt text (should include Gemma chat template tags)
     * @param maxTokens Unused — Llamatik uses llama.cpp defaults
     * @param temperature Unused — Llamatik uses llama.cpp defaults
     * @return Flow of token strings
     */
    fun generateStream(
        prompt: String,
        maxTokens: Int = 512,
        temperature: Float = 0.3f
    ): Flow<String> = callbackFlow {
        state = State.Generating
        Log.d(TAG, "Streaming generation on-device (prompt: ${prompt.length} chars)")

        LlamaBridge.generateStream(prompt, object : GenStream {
            override fun onDelta(text: String) {
                trySend(text)
            }

            override fun onComplete() {
                state = State.Ready
                Log.d(TAG, "Streaming generation complete")
                close()
            }

            override fun onError(message: String) {
                state = State.Ready
                Log.e(TAG, "Streaming generation error: $message")
                close(RuntimeException("MedGemma streaming failed: $message"))
            }
        })

        awaitClose {
            LlamaBridge.nativeCancelGenerate()
        }
    }.flowOn(Dispatchers.IO)

    /**
     * Release resources.
     */
    fun close() {
        if (isAvailable) {
            try {
                LlamaBridge.shutdown()
            } catch (e: Exception) {
                Log.w(TAG, "Error during shutdown: ${e.message}")
            }
        }
        isInitialized = false
        isAvailable = false
        state = State.NotInitialized
        Log.d(TAG, "MedGemma engine closed")
    }
}
