package org.who.chw.clinical.brain2

import android.util.Log
import org.who.chw.clinical.brain1.SearchResult

/**
 * Result of guardrail validation.
 */
data class GuardrailResult(
    val passed: Boolean,
    val reason: String?,
    val fullValidation: String,
    val criteria: Map<String, Boolean> = emptyMap()
)

/**
 * Safety guardrail validator using MedGemma self-critique.
 *
 * Performs a second inference pass to verify that the generated clinical
 * summary is grounded in the source guideline chunks and is safe.
 *
 * Validates:
 * - GROUNDING: Claims supported by source guidelines
 * - ACCURACY: Dosages and treatment steps match sources
 * - COMPLETENESS: Critical safety info not omitted
 * - NO_FABRICATION: No invented clinical information
 * - APPROPRIATE_SCOPE: Within CHW scope of practice
 */
class GuardrailValidator(private val engine: MedGemmaEngine) {

    companion object {
        private const val TAG = "GuardrailValidator"
        private const val MAX_VALIDATION_TOKENS = 300
        private const val VALIDATION_TEMPERATURE = 0.1f

        private val CRITERIA = listOf(
            "GROUNDING", "ACCURACY", "COMPLETENESS",
            "NO_FABRICATION", "APPROPRIATE_SCOPE"
        )
    }

    /**
     * Validate a generated summary against source chunks.
     *
     * @param query Original clinical question
     * @param summary Generated summary to validate
     * @param sourceChunks Source chunks the summary should be grounded in
     * @return GuardrailResult with pass/fail and details
     */
    suspend fun validate(
        query: String,
        summary: String,
        sourceChunks: List<SearchResult>
    ): GuardrailResult {
        if (!engine.isReady()) {
            Log.w(TAG, "Engine not ready, skipping guardrail")
            return GuardrailResult(
                passed = true, // Permissive when guardrail unavailable
                reason = "Guardrail skipped (engine not ready)",
                fullValidation = ""
            )
        }

        return try {
            val prompt = ClinicalPrompts.guardrailPrompt(query, summary, sourceChunks)

            val validation = engine.generate(
                prompt = prompt,
                maxTokens = MAX_VALIDATION_TOKENS,
                temperature = VALIDATION_TEMPERATURE
            )

            // Parse the structured validation response
            val passed = parseOverallResult(validation)
            val reason = parseFailureReason(validation)
            val criteria = parseCriteria(validation)

            Log.d(TAG, "Guardrail: ${if (passed) "PASS" else "FAIL"} - $reason")

            GuardrailResult(
                passed = passed,
                reason = reason,
                fullValidation = validation,
                criteria = criteria
            )
        } catch (e: Exception) {
            Log.e(TAG, "Guardrail validation failed", e)
            // Permissive on error - don't block results due to guardrail failure
            GuardrailResult(
                passed = true,
                reason = "Guardrail error: ${e.message}",
                fullValidation = ""
            )
        }
    }

    private fun parseOverallResult(validation: String): Boolean {
        val upper = validation.uppercase()
        // Look for "OVERALL: PASS" pattern
        val overallLine = upper.lines().find { it.trimStart().startsWith("OVERALL:") }
        return overallLine?.contains("PASS") == true
    }

    private fun parseFailureReason(validation: String): String? {
        val lines = validation.lines()
        val reasonLine = lines.find { it.trimStart().uppercase().startsWith("REASON:") }
        return reasonLine?.substringAfter(":")?.trim()?.takeIf { it.isNotBlank() }
    }

    private fun parseCriteria(validation: String): Map<String, Boolean> {
        val result = mutableMapOf<String, Boolean>()
        val upper = validation.uppercase()

        for (criterion in CRITERIA) {
            val line = upper.lines().find { it.trimStart().startsWith("$criterion:") }
            if (line != null) {
                result[criterion] = line.contains("PASS")
            }
        }

        return result
    }
}
