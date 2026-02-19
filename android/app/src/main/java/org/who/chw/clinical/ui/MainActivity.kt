package org.who.chw.clinical.ui

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import org.who.chw.clinical.brain1.EmbeddingEngine
import org.who.chw.clinical.brain1.HighRiskDetector
import org.who.chw.clinical.brain1.SearchService
import org.who.chw.clinical.brain2.GuardrailValidator
import org.who.chw.clinical.brain2.MedGemmaEngine
import org.who.chw.clinical.brain2.SynthesisService
import org.who.chw.clinical.data.ChunkRepository
import org.who.chw.clinical.data.DatabaseHelper
import org.who.chw.clinical.ui.theme.CHWClinicalTheme

/**
 * Main activity for CHW Clinical Support application.
 *
 * Phase 3 adds Brain 2: MedGemma synthesis with guardrail validation.
 */
class MainActivity : ComponentActivity() {

    companion object {
        private const val TAG = "MainActivity"
    }

    private lateinit var databaseHelper: DatabaseHelper
    private lateinit var searchService: SearchService
    private lateinit var highRiskDetector: HighRiskDetector
    private lateinit var medGemmaEngine: MedGemmaEngine
    private lateinit var synthesisService: SynthesisService

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Initialize components
        initializeServices()

        setContent {
            CHWClinicalTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    var isInitialized by remember { mutableStateOf(false) }
                    var isBrain2Ready by remember { mutableStateOf(false) }
                    var brain2Error by remember { mutableStateOf<String?>(null) }
                    var initError by remember { mutableStateOf<String?>(null) }

                    // Initialize Brain 1 (critical) and Brain 2 (optional)
                    LaunchedEffect(Unit) {
                        try {
                            // Brain 1: Must succeed
                            searchService.initialize()
                            highRiskDetector.initialize()
                            isInitialized = true

                            // Brain 2: Best-effort (don't block on failure)
                            // On-device MedGemma via llama.cpp — first run extracts
                            // ~2.5GB GGUF from assets to cache (may take 10-30s)
                            try {
                                medGemmaEngine.initialize(applicationContext)
                                isBrain2Ready = medGemmaEngine.isReady()
                                if (!isBrain2Ready) {
                                    val engineState = medGemmaEngine.state
                                    if (engineState is MedGemmaEngine.State.Error) {
                                        brain2Error = engineState.message
                                    }
                                }
                                Log.d(TAG, "Brain 2 ready: $isBrain2Ready")
                            } catch (e: Exception) {
                                brain2Error = e.message ?: "Unknown error"
                                Log.w(TAG, "Brain 2 init failed (non-fatal): ${e.message}")
                            }
                        } catch (e: Exception) {
                            initError = "Failed to initialize: ${e.localizedMessage}"
                        }
                    }

                    SearchScreen(
                        searchService = searchService,
                        highRiskDetector = highRiskDetector,
                        synthesisService = synthesisService,
                        isInitialized = isInitialized,
                        isBrain2Ready = isBrain2Ready,
                        brain2Error = brain2Error,
                        initError = initError
                    )
                }
            }
        }
    }

    private fun initializeServices() {
        // Brain 1: On-device retrieval
        databaseHelper = DatabaseHelper(applicationContext)
        val chunkRepository = ChunkRepository(databaseHelper)
        val embeddingEngine = EmbeddingEngine(applicationContext)
        searchService = SearchService(embeddingEngine, chunkRepository)
        highRiskDetector = HighRiskDetector(databaseHelper)

        // Brain 2: MedGemma synthesis
        medGemmaEngine = MedGemmaEngine()
        val guardrailValidator = GuardrailValidator(medGemmaEngine)
        synthesisService = SynthesisService(medGemmaEngine, guardrailValidator)
    }

    override fun onDestroy() {
        super.onDestroy()
        searchService.close()
        medGemmaEngine.close()
        databaseHelper.close()
    }
}
