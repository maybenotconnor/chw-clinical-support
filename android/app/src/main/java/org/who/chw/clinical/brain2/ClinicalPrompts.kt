package org.who.chw.clinical.brain2

import org.who.chw.clinical.brain1.HighRiskAlert
import org.who.chw.clinical.brain1.SearchResult

/**
 * Clinical prompt templates for MedGemma synthesis.
 *
 * Kotlin port of extraction/src/clinical_prompts.py.
 * These prompts are designed for MedGemma 1.5 4B-it to:
 * 1. Synthesize clinical summaries from retrieved guideline chunks
 * 2. Validate summaries against source material (guardrail)
 */
object ClinicalPrompts {

    private const val MAX_CONTEXT_CHARS = 1500
    private const val MAX_GUARDRAIL_CONTEXT_CHARS = 3000

    /**
     * Wrap prompt text in Gemma-style chat template tags.
     * MedGemma (based on Gemma) expects this format for instruction-tuned inference.
     */
    private fun wrapGemmaPrompt(content: String): String {
        return "<start_of_turn>user\n${content.trim()}\n<end_of_turn>\n<start_of_turn>model\n"
    }

    /**
     * Format retrieved chunks as numbered context for prompts.
     */
    fun formatChunks(results: List<SearchResult>, maxChars: Int = MAX_CONTEXT_CHARS): String {
        val builder = StringBuilder()
        var totalChars = 0

        for ((i, result) in results.withIndex()) {
            val headingPath = if (result.headings.isNotEmpty()) {
                result.headings.joinToString(" > ")
            } else {
                "General"
            }
            val pageInfo = result.pageNumber?.let { " (p.$it)" } ?: ""
            val entry = "[${i + 1}] $headingPath$pageInfo\n${result.content}"

            if (totalChars + entry.length > maxChars) break

            if (i > 0) builder.append("\n\n")
            builder.append(entry)
            totalChars += entry.length
        }

        return builder.toString()
    }

    /**
     * Format high-risk alerts as warnings.
     */
    fun formatAlerts(alerts: List<HighRiskAlert>): String {
        if (alerts.isEmpty()) return ""

        val high = alerts.filter { it.severity == HighRiskAlert.Severity.HIGH }
        val medium = alerts.filter { it.severity == HighRiskAlert.Severity.MEDIUM }

        val lines = mutableListOf<String>()
        if (high.isNotEmpty()) {
            lines.add("DANGER SIGNS DETECTED: ${high.joinToString(", ") { it.term }}")
        }
        if (medium.isNotEmpty()) {
            lines.add("Caution terms found: ${medium.joinToString(", ") { it.term }}")
        }

        return lines.joinToString("\n")
    }

    /**
     * Build the clinical synthesis prompt.
     *
     * Takes a user query and retrieved guideline chunks, produces a prompt
     * that asks MedGemma to synthesize a clinical summary grounded in the
     * provided evidence.
     */
    fun synthesisPrompt(
        query: String,
        results: List<SearchResult>,
        alerts: List<HighRiskAlert> = emptyList()
    ): String {
        val context = formatChunks(results)
        val alertText = formatAlerts(alerts)

        val alertSection = if (alertText.isNotEmpty()) {
            """

⚠️ SAFETY ALERTS:
$alertText
You MUST prominently address these safety concerns in your response.
"""
        } else {
            ""
        }

        val body = """You are a clinical decision support assistant for Community Health Workers (CHWs) in Uganda. Your role is to synthesize clinical guidelines into clear, actionable guidance.

CLINICAL GUIDELINE EXCERPTS:
$context
$alertSection
CHW QUESTION: $query

INSTRUCTIONS:
1. Answer ONLY using information from the guideline excerpts above
2. Use simple, clear language appropriate for CHWs with basic medical training
3. Structure your response with clear sections when appropriate
4. Include specific dosages, age ranges, and treatment steps when available
5. If danger signs are mentioned, list them prominently at the top
6. If the guidelines do not contain enough information to answer, say so clearly
7. NEVER fabricate clinical information not present in the excerpts
8. Include relevant page references using [p.X] format

Provide a concise clinical summary (150-300 words):"""

        return wrapGemmaPrompt(body)
    }

    /**
     * Build the guardrail validation prompt.
     *
     * Checks whether the generated summary is grounded in the source chunks
     * and is clinically safe.
     */
    fun guardrailPrompt(
        query: String,
        summary: String,
        results: List<SearchResult>
    ): String {
        val context = formatChunks(results, MAX_GUARDRAIL_CONTEXT_CHARS)

        val body = """You are a clinical safety validator. Your job is to verify that a generated clinical summary is grounded in source guidelines and is safe for Community Health Workers.

SOURCE GUIDELINES:
$context

QUESTION: $query

GENERATED SUMMARY:
$summary

VALIDATION CRITERIA:
1. GROUNDING: Every clinical claim in the summary must be supported by the source guidelines
2. ACCURACY: Dosages, age ranges, and treatment steps must exactly match the sources
3. COMPLETENESS: Critical safety information (danger signs, referral criteria) must not be omitted
4. NO FABRICATION: The summary must not contain clinical information absent from the sources
5. APPROPRIATE SCOPE: The summary should not recommend actions beyond CHW scope of practice

For each criterion, evaluate PASS or FAIL with a brief explanation.

Respond in this exact format:
GROUNDING: [PASS/FAIL] - [explanation]
ACCURACY: [PASS/FAIL] - [explanation]
COMPLETENESS: [PASS/FAIL] - [explanation]
NO_FABRICATION: [PASS/FAIL] - [explanation]
APPROPRIATE_SCOPE: [PASS/FAIL] - [explanation]

OVERALL: [PASS/FAIL]
REASON: [one sentence summary if FAIL]"""

        return wrapGemmaPrompt(body)
    }

    /**
     * Build image analysis prompt for multimodal MedGemma.
     */
    fun imageAnalysisPrompt(additionalContext: String? = null): String {
        val contextLine = if (additionalContext != null) {
            "\nAdditional context from the health worker: $additionalContext"
        } else {
            ""
        }

        val body = """You are a clinical image analysis assistant for Community Health Workers (CHWs). A CHW has taken a photo of a patient's condition for guidance.
$contextLine
Analyze this clinical image and provide:

1. OBSERVATION: Describe what you observe in clinical terms (appearance, location, characteristics)
2. POSSIBLE CONDITIONS: List 2-3 possible conditions that could match these observations
3. KEY FEATURES: Note specific features that would help narrow the differential
4. SEARCH TERMS: Suggest 2-3 search terms to look up in clinical guidelines

IMPORTANT:
- Do NOT provide a definitive diagnosis
- This is for guideline lookup assistance only
- Always recommend the CHW consult guidelines and refer if uncertain
- Be specific enough to enable useful guideline searches

Provide your analysis:"""

        return wrapGemmaPrompt(body)
    }
}
