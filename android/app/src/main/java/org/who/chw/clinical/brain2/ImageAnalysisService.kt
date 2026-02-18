package org.who.chw.clinical.brain2

import android.net.Uri
import android.util.Log

/**
 * Result of image analysis.
 */
data class ImageAnalysisResult(
    val description: String,
    val searchQuery: String,
    val rawAnalysis: String
)

/**
 * Image analysis service using MedGemma multimodal capabilities.
 *
 * Workflow:
 * 1. CHW captures a photo of a clinical condition
 * 2. MedGemma analyzes the image and generates a clinical description
 * 3. The description is used as a search query for Brain 1
 * 4. Brain 1 results are synthesized with Brain 2
 *
 * Note: Multimodal support depends on the MedGemma deployment.
 * When multimodal is not available, falls back to text-based
 * description from the CHW.
 */
class ImageAnalysisService(private val engine: MedGemmaEngine) {

    companion object {
        private const val TAG = "ImageAnalysisService"
        private const val MAX_ANALYSIS_TOKENS = 300
        private const val ANALYSIS_TEMPERATURE = 0.3f
    }

    /**
     * Whether multimodal image analysis is available.
     *
     * Currently text-only; multimodal requires MedGemma mmproj support.
     */
    fun isMultimodalAvailable(): Boolean = false // TODO: Enable when multimodal works

    /**
     * Analyze a clinical image and generate search terms.
     *
     * Currently uses text description from CHW since multimodal
     * on-device inference requires additional setup.
     *
     * @param imageUri URI of the captured image
     * @param userDescription CHW's text description of the condition
     * @return ImageAnalysisResult with search query
     */
    suspend fun analyzeImage(
        imageUri: Uri?,
        userDescription: String
    ): ImageAnalysisResult {
        if (!engine.isReady()) {
            // Fallback: use the user's description directly as search query
            return ImageAnalysisResult(
                description = userDescription,
                searchQuery = userDescription,
                rawAnalysis = "[MedGemma not available - using direct description]"
            )
        }

        return try {
            if (isMultimodalAvailable() && imageUri != null) {
                analyzeWithVision(imageUri, userDescription)
            } else {
                analyzeFromDescription(userDescription)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Image analysis failed", e)
            // Fallback to direct description
            ImageAnalysisResult(
                description = userDescription,
                searchQuery = userDescription,
                rawAnalysis = "[Analysis failed: ${e.message}]"
            )
        }
    }

    /**
     * Analyze using text description only (current implementation).
     * MedGemma refines the CHW's description into clinical search terms.
     */
    private suspend fun analyzeFromDescription(description: String): ImageAnalysisResult {
        val prompt = """A Community Health Worker describes a patient's condition:
"$description"

Based on this description, provide:
1. The most likely clinical condition or category
2. A concise search query (5-15 words) to look up treatment guidelines

Output ONLY the search query on the last line, nothing else after it.

Analysis:"""

        val analysis = engine.generate(
            prompt = prompt,
            maxTokens = MAX_ANALYSIS_TOKENS,
            temperature = ANALYSIS_TEMPERATURE
        )

        // Extract search query from last non-empty line
        val searchQuery = analysis.lines()
            .map { it.trim() }
            .lastOrNull { it.isNotBlank() }
            ?: description

        return ImageAnalysisResult(
            description = description,
            searchQuery = searchQuery,
            rawAnalysis = analysis
        )
    }

    /**
     * Analyze with multimodal vision (future implementation).
     */
    private suspend fun analyzeWithVision(
        imageUri: Uri,
        userDescription: String
    ): ImageAnalysisResult {
        // TODO: Implement when MedGemma multimodal is available on-device
        // This would encode the image and send to MedGemma's vision model
        Log.d(TAG, "Multimodal analysis not yet implemented, falling back to text")
        return analyzeFromDescription(userDescription)
    }
}
