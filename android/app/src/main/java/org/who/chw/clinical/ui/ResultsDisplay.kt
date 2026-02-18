package org.who.chw.clinical.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.who.chw.clinical.brain1.HighRiskAlert
import org.who.chw.clinical.brain1.SearchResult
import org.who.chw.clinical.brain2.SynthesisState

/**
 * Display search results as a scrollable list.
 *
 * Phase 3 adds AI summary display above results.
 *
 * @param results List of search results to display
 * @param alerts Optional list of high-risk alerts (shown above results)
 * @param synthesisState Current state of Brain 2 synthesis
 * @param modifier Modifier for the container
 */
@Composable
fun ResultsDisplay(
    results: List<SearchResult>,
    alerts: List<HighRiskAlert> = emptyList(),
    synthesisState: SynthesisState = SynthesisState.Idle,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier.fillMaxSize()) {
        // High-risk warning banner (if any alerts)
        HighRiskWarning(alerts = alerts)

        // AI Summary (Brain 2)
        SummaryDisplay(synthesisState = synthesisState)

        // Results count
        Text(
            text = "${results.size} results found",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
        )

        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp)
        ) {
            itemsIndexed(results) { index, result ->
                ResultCard(result = result, rank = index + 1)
            }
        }
    }
}

@Composable
fun ResultCard(
    result: SearchResult,
    rank: Int = 0,
    modifier: Modifier = Modifier
) {
    var isExpanded by remember { mutableStateOf(false) }
    val hasExpandedContent = result.expandedContent != null

    Card(
        modifier = modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            // Top row: Rank and Page number
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Rank badge
                Surface(
                    color = MaterialTheme.colorScheme.primaryContainer,
                    shape = MaterialTheme.shapes.small
                ) {
                    Text(
                        text = "#$rank",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                    )
                }

                // Page number with icon
                result.pageNumber?.let { page ->
                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.MenuBook,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "Page $page",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Heading path (section breadcrumb)
            if (result.headings.isNotEmpty()) {
                Text(
                    text = result.headings.joinToString(" > "),
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.primary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )

                Spacer(modifier = Modifier.height(8.dp))
            }

            // Content - show expanded if available and toggled, otherwise show snippet
            val displayContent = if (isExpanded && hasExpandedContent) {
                result.expandedContent!!
            } else {
                result.expandedContent?.take(800) ?: result.content
            }

            Text(
                text = displayContent,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = if (isExpanded) Int.MAX_VALUE else 12,
                overflow = TextOverflow.Ellipsis
            )

            // Show more/less toggle if there's expanded content
            if (hasExpandedContent && (result.expandedContent!!.length > 800 || isExpanded)) {
                Spacer(modifier = Modifier.height(8.dp))
                TextButton(
                    onClick = { isExpanded = !isExpanded },
                    modifier = Modifier.align(Alignment.End)
                ) {
                    Text(
                        text = if (isExpanded) "Show less" else "Show full section",
                        style = MaterialTheme.typography.labelMedium
                    )
                }
            }
        }
    }
}
