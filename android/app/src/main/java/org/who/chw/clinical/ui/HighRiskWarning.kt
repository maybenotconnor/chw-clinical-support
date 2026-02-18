package org.who.chw.clinical.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import org.who.chw.clinical.brain1.HighRiskAlert
import org.who.chw.clinical.ui.theme.CHWClinicalTheme

// Custom colors for warnings (not in standard Material palette)
private val HighSeverityRed = Color(0xFFD32F2F)      // Red 700
private val HighSeverityOnRed = Color(0xFFFFFFFF)    // White
private val MediumSeverityAmber = Color(0xFFF57C00)  // Orange 700
private val MediumSeverityOnAmber = Color(0xFF000000) // Black

/**
 * Warning banner displayed when high-risk clinical terms are detected.
 *
 * Shows a prominent colored card with:
 * - Red background for HIGH severity (danger signs)
 * - Amber/orange background for MEDIUM severity (caution)
 * - List of detected terms with categories
 *
 * This warning appears above search results and does NOT block access.
 */
@Composable
fun HighRiskWarning(
    alerts: List<HighRiskAlert>,
    modifier: Modifier = Modifier
) {
    AnimatedVisibility(
        visible = alerts.isNotEmpty(),
        enter = fadeIn() + expandVertically(),
        exit = fadeOut() + shrinkVertically()
    ) {
        val hasHighSeverity = alerts.any { it.severity == HighRiskAlert.Severity.HIGH }

        val backgroundColor = if (hasHighSeverity) HighSeverityRed else MediumSeverityAmber
        val contentColor = if (hasHighSeverity) HighSeverityOnRed else MediumSeverityOnAmber

        Card(
            colors = CardDefaults.cardColors(
                containerColor = backgroundColor
            ),
            modifier = modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp)
        ) {
            Column(
                modifier = Modifier.padding(16.dp)
            ) {
                // Header with icon
                Row(
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = "Warning",
                        tint = contentColor
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = if (hasHighSeverity) "DANGER SIGNS DETECTED" else "Caution Required",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = contentColor
                    )
                }

                Spacer(Modifier.height(8.dp))

                // Subheading
                Text(
                    text = if (hasHighSeverity)
                        "These results contain indicators requiring immediate attention:"
                    else
                        "These results contain terms requiring caution:",
                    style = MaterialTheme.typography.bodyMedium,
                    color = contentColor.copy(alpha = 0.9f)
                )

                Spacer(Modifier.height(8.dp))

                // List of alerts
                alerts.take(5).forEach { alert ->  // Limit to 5 to avoid clutter
                    Text(
                        text = "• ${alert.term} (${alert.category})",
                        style = MaterialTheme.typography.bodyMedium,
                        color = contentColor
                    )
                }

                // Show count if more than 5
                if (alerts.size > 5) {
                    Text(
                        text = "...and ${alerts.size - 5} more",
                        style = MaterialTheme.typography.bodySmall,
                        color = contentColor.copy(alpha = 0.7f)
                    )
                }
            }
        }
    }
}

/**
 * Compact version of the warning for inline display.
 */
@Composable
fun HighRiskBadge(
    severity: HighRiskAlert.Severity,
    modifier: Modifier = Modifier
) {
    val backgroundColor = when (severity) {
        HighRiskAlert.Severity.HIGH -> HighSeverityRed
        HighRiskAlert.Severity.MEDIUM -> MediumSeverityAmber
    }
    val contentColor = when (severity) {
        HighRiskAlert.Severity.HIGH -> HighSeverityOnRed
        HighRiskAlert.Severity.MEDIUM -> MediumSeverityOnAmber
    }

    Card(
        colors = CardDefaults.cardColors(containerColor = backgroundColor),
        modifier = modifier
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
        ) {
            Icon(
                imageVector = Icons.Default.Warning,
                contentDescription = null,
                tint = contentColor,
                modifier = Modifier.height(16.dp)
            )
            Spacer(Modifier.width(4.dp))
            Text(
                text = if (severity == HighRiskAlert.Severity.HIGH) "DANGER" else "CAUTION",
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = contentColor
            )
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun HighRiskWarningPreviewHigh() {
    CHWClinicalTheme {
        HighRiskWarning(
            alerts = listOf(
                HighRiskAlert("danger signs", "General", HighRiskAlert.Severity.HIGH),
                HighRiskAlert("refer immediately", "Referral", HighRiskAlert.Severity.HIGH),
                HighRiskAlert("convulsions", "Neurological", HighRiskAlert.Severity.HIGH)
            )
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun HighRiskWarningPreviewMedium() {
    CHWClinicalTheme {
        HighRiskWarning(
            alerts = listOf(
                HighRiskAlert("severe headache", "Neurological", HighRiskAlert.Severity.MEDIUM),
                HighRiskAlert("refer to health facility", "Referral", HighRiskAlert.Severity.MEDIUM)
            )
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun HighRiskBadgePreview() {
    CHWClinicalTheme {
        Row {
            HighRiskBadge(HighRiskAlert.Severity.HIGH)
            Spacer(Modifier.width(8.dp))
            HighRiskBadge(HighRiskAlert.Severity.MEDIUM)
        }
    }
}
