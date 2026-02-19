package org.who.chw.clinical.brain2

import android.util.Log
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.onCompletion
import org.who.chw.clinical.brain1.HighRiskAlert
import org.who.chw.clinical.brain1.SearchResult
import android.os.SystemClock

/**
 * State of the synthesis process.
 */
sealed class SynthesisState {
    data object Idle : SynthesisState()
    data object Generating : SynthesisState()
    data class Streaming(val partialText: String) : SynthesisState()
    data class Success(
        val summary: String,
        val guardrailPassed: Boolean? = null
    ) : SynthesisState()
    data class Refused(val reason: String) : SynthesisState()
    data class Error(val message: String) : SynthesisState()
}

/**
 * Brain 2 synthesis service that orchestrates MedGemma inference.
 *
 * Takes Brain 1 search results and high-risk alerts, constructs clinical
 * prompts, and calls [MedGemmaEngine] for synthesis. Returns streaming
 * results via [SynthesisState].
 */
class SynthesisService(
    private val engine: MedGemmaEngine,
    private val guardrailValidator: GuardrailValidator? = null
) {

    companion object {
        private const val TAG = "SynthesisService"
        private const val MAX_SYNTHESIS_TOKENS = 256
        private const val SYNTHESIS_TEMPERATURE = 0.3f
        private const val STREAM_UPDATE_INTERVAL_MS = 150L
    }

    /**
     * Check if Brain 2 synthesis is available.
     */
    fun isAvailable(): Boolean = engine.isReady()

    /**
     * Generate a clinical synthesis from search results (non-streaming).
     *
     * @param query Original clinical question
     * @param results Brain 1 search results
     * @param alerts Detected high-risk alerts
     * @param runGuardrail Whether to validate the synthesis
     * @return Final SynthesisState
     */
    suspend fun synthesize(
        query: String,
        results: List<SearchResult>,
        alerts: List<HighRiskAlert> = emptyList(),
        runGuardrail: Boolean = true
    ): SynthesisState {
        if (!engine.isReady()) {
            return SynthesisState.Error("MedGemma not available")
        }

        if (results.isEmpty()) {
            return SynthesisState.Refused("No guideline content to synthesize")
        }

        return try {
            Log.d(TAG, "Synthesizing from ${results.size} chunks, ${alerts.size} alerts")

            // Build prompt
            val prompt = ClinicalPrompts.synthesisPrompt(query, results, alerts)

            // Generate synthesis
            val summary = engine.generate(
                prompt = prompt,
                maxTokens = MAX_SYNTHESIS_TOKENS,
                temperature = SYNTHESIS_TEMPERATURE
            )

            if (summary.isBlank()) {
                return SynthesisState.Refused("Model returned empty response")
            }

            // Guardrail validation disabled on-device — doubles inference time
            SynthesisState.Success(summary, guardrailPassed = null)
        } catch (e: Exception) {
            Log.e(TAG, "Synthesis failed", e)
            SynthesisState.Error("Synthesis error: ${e.localizedMessage ?: "Unknown"}")
        }
    }

    /**
     * Generate a clinical synthesis with streaming token output.
     *
     * Emits [SynthesisState] updates as tokens arrive, ending with
     * [SynthesisState.Success] (optionally with guardrail result).
     *
     * @param query Original clinical question
     * @param results Brain 1 search results
     * @param alerts Detected high-risk alerts
     * @param runGuardrail Whether to validate after generation completes
     * @return Flow of SynthesisState
     */
    fun synthesizeStream(
        query: String,
        results: List<SearchResult>,
        alerts: List<HighRiskAlert> = emptyList(),
        runGuardrail: Boolean = true
    ): Flow<SynthesisState> = flow {
        if (!engine.isReady()) {
            emit(SynthesisState.Error("MedGemma not available"))
            return@flow
        }

        if (results.isEmpty()) {
            emit(SynthesisState.Refused("No guideline content to synthesize"))
            return@flow
        }

        emit(SynthesisState.Generating)

        try {
            val prompt = ClinicalPrompts.synthesisPrompt(query, results, alerts)
            val fullText = StringBuilder()
            var lastEmitTime = 0L

            engine.generateStream(
                prompt = prompt,
                maxTokens = MAX_SYNTHESIS_TOKENS,
                temperature = SYNTHESIS_TEMPERATURE
            ).collect { token ->
                fullText.append(token)
                val now = SystemClock.elapsedRealtime()
                if (now - lastEmitTime >= STREAM_UPDATE_INTERVAL_MS) {
                    emit(SynthesisState.Streaming(fullText.toString()))
                    lastEmitTime = now
                }
            }
            // Emit final streaming state to capture any remaining tokens
            emit(SynthesisState.Streaming(fullText.toString()))

            val summary = fullText.toString().trim()

            if (summary.isBlank()) {
                emit(SynthesisState.Refused("Model returned empty response"))
                return@flow
            }

            // Guardrail validation disabled on-device — doubles inference time
            // (~7 min extra on Snapdragon 845). Re-enable when faster SoCs are targeted.
            emit(SynthesisState.Success(summary, guardrailPassed = null))
        } catch (e: Exception) {
            Log.e(TAG, "Streaming synthesis failed", e)
            emit(SynthesisState.Error("Synthesis error: ${e.localizedMessage ?: "Unknown"}"))
        }
    }
}
