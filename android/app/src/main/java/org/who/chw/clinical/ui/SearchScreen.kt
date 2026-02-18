package org.who.chw.clinical.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.who.chw.clinical.R
import org.who.chw.clinical.brain1.HighRiskAlert
import org.who.chw.clinical.brain1.HighRiskDetector
import org.who.chw.clinical.brain1.SearchService
import org.who.chw.clinical.brain1.SearchState
import org.who.chw.clinical.brain2.SynthesisService
import org.who.chw.clinical.brain2.SynthesisState

private val MedGemmaBlue = Color(0xFF1A73E8)
private val OnlineGreen = Color(0xFF34A853)

/**
 * Main search screen composable.
 *
 * Integrates Brain 1 (offline retrieval) and Brain 2 (MedGemma synthesis)
 * with camera capture for multimodal clinical queries.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchScreen(
    searchService: SearchService,
    highRiskDetector: HighRiskDetector?,
    synthesisService: SynthesisService?,
    isInitialized: Boolean,
    isBrain2Ready: Boolean = false,
    initError: String?,
    modifier: Modifier = Modifier
) {
    var queryText by remember { mutableStateOf("") }
    var searchState by remember { mutableStateOf<SearchState>(SearchState.Idle) }
    var highRiskAlerts by remember { mutableStateOf<List<HighRiskAlert>>(emptyList()) }
    var synthesisState by remember { mutableStateOf<SynthesisState>(SynthesisState.Idle) }
    var capturedImageUri by remember { mutableStateOf<Uri?>(null) }
    val coroutineScope = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current

    // Camera launcher
    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicturePreview()
    ) { bitmap ->
        if (bitmap != null) {
            // For now, prompt user to describe what they photographed
            // Full multimodal analysis will use ImageAnalysisService
            queryText = "skin condition rash" // Placeholder - in production, use image analysis
        }
    }

    fun performSearch() {
        if (queryText.isBlank()) return

        focusManager.clearFocus()
        coroutineScope.launch {
            searchState = SearchState.Loading
            highRiskAlerts = emptyList()
            synthesisState = SynthesisState.Idle

            val result = searchService.search(queryText)
            searchState = result

            // Detect high-risk terms in results
            if (result is SearchState.Success && highRiskDetector != null) {
                highRiskAlerts = highRiskDetector.detectRisks(result.results)
            }

            // Trigger Brain 2 synthesis if available
            if (result is SearchState.Success && synthesisService != null && synthesisService.isAvailable()) {
                synthesisService.synthesizeStream(
                    query = queryText,
                    results = result.results,
                    alerts = highRiskAlerts,
                    runGuardrail = true
                ).collect { state ->
                    synthesisState = state
                }
            }
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp)
    ) {
        // Header with app title and status badges
        Spacer(modifier = Modifier.height(16.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = stringResource(R.string.app_name),
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )
                Text(
                    text = stringResource(R.string.app_subtitle),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            // Status badges
            Column(
                horizontalAlignment = Alignment.End,
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                // Brain 1 always-on badge
                StatusBadge(
                    text = stringResource(R.string.brain1_label),
                    color = OnlineGreen,
                    isActive = isInitialized
                )

                // Brain 2 status badge
                StatusBadge(
                    text = if (isBrain2Ready) stringResource(R.string.brain2_ready) else stringResource(R.string.brain2_offline),
                    color = if (isBrain2Ready) MedGemmaBlue else MaterialTheme.colorScheme.outline,
                    isActive = isBrain2Ready
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Initialization error
        AnimatedVisibility(visible = initError != null) {
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 16.dp)
            ) {
                Text(
                    text = initError ?: "",
                    color = MaterialTheme.colorScheme.onErrorContainer,
                    modifier = Modifier.padding(16.dp)
                )
            }
        }

        // Search Input with camera button
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedTextField(
                value = queryText,
                onValueChange = { queryText = it },
                label = { Text(stringResource(R.string.search_hint)) },
                modifier = Modifier.weight(1f),
                enabled = isInitialized && initError == null,
                trailingIcon = {
                    IconButton(
                        onClick = { performSearch() },
                        enabled = isInitialized && queryText.isNotBlank()
                    ) {
                        Icon(
                            Icons.Default.Search,
                            contentDescription = stringResource(R.string.search_button)
                        )
                    }
                },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(
                    onSearch = { performSearch() }
                ),
                singleLine = true
            )

            // Camera button
            FilledTonalIconButton(
                onClick = { cameraLauncher.launch(null) },
                enabled = isInitialized && initError == null
            ) {
                Icon(
                    Icons.Default.CameraAlt,
                    contentDescription = stringResource(R.string.camera_button)
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Loading indicator while initializing
        if (!isInitialized && initError == null) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator()
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "Loading clinical guidelines...",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            return@Column
        }

        // Results Area
        when (val state = searchState) {
            is SearchState.Idle -> {
                EmptyStateMessage()
            }
            is SearchState.Loading -> {
                LoadingIndicator()
            }
            is SearchState.Success -> {
                ResultsDisplay(
                    results = state.results,
                    alerts = highRiskAlerts,
                    synthesisState = synthesisState
                )
            }
            is SearchState.Error -> {
                ErrorMessage(message = state.message)
            }
        }
    }
}

/**
 * Status badge showing Brain 1/Brain 2 availability.
 */
@Composable
private fun StatusBadge(
    text: String,
    color: Color,
    isActive: Boolean,
    modifier: Modifier = Modifier
) {
    Surface(
        color = color.copy(alpha = if (isActive) 0.12f else 0.05f),
        shape = MaterialTheme.shapes.small,
        modifier = modifier
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
        ) {
            Icon(
                imageVector = if (isActive) Icons.Default.SmartToy else Icons.Default.CloudOff,
                contentDescription = null,
                tint = if (isActive) color else MaterialTheme.colorScheme.outline,
                modifier = Modifier.size(12.dp)
            )
            Spacer(Modifier.width(4.dp))
            Text(
                text = text,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Medium,
                color = if (isActive) color else MaterialTheme.colorScheme.outline
            )
        }
    }
}

@Composable
private fun EmptyStateMessage() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = stringResource(R.string.empty_state_title),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface
            )

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = stringResource(R.string.empty_state),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(24.dp))

            Text(
                text = stringResource(R.string.powered_by),
                style = MaterialTheme.typography.labelSmall,
                color = MedGemmaBlue.copy(alpha = 0.7f)
            )
        }
    }
}

@Composable
private fun LoadingIndicator() {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator()
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = stringResource(R.string.loading),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun ErrorMessage(message: String) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp),
        contentAlignment = Alignment.Center
    ) {
        Card(
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.errorContainer
            )
        ) {
            Text(
                text = message,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onErrorContainer,
                modifier = Modifier.padding(16.dp)
            )
        }
    }
}
