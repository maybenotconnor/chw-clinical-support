package org.who.chw.clinical.brain1

import android.database.sqlite.SQLiteDatabase
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.who.chw.clinical.data.DatabaseHelper

/**
 * High-risk alert detected in search results.
 */
data class HighRiskAlert(
    val term: String,
    val category: String,
    val severity: Severity
) {
    enum class Severity {
        HIGH,   // Red warning - immediate action needed
        MEDIUM  // Amber warning - caution required
    }
}

/**
 * Internal representation of a high-risk term from the database.
 */
private data class HighRiskTerm(
    val term: String,
    val category: String,
    val severity: String
)

/**
 * Detector for high-risk clinical terms in search results.
 *
 * Scans retrieved content for clinically-curated danger signs and
 * referral indicators that require immediate attention or caution.
 *
 * High-risk terms are stored in the database and loaded at initialization.
 */
class HighRiskDetector(private val dbHelper: DatabaseHelper) {

    companion object {
        private const val TAG = "HighRiskDetector"
    }

    /**
     * Cached high-risk terms loaded from database.
     */
    private var terms: List<HighRiskTerm> = emptyList()
    private var isInitialized = false

    /**
     * Initialize the detector by loading terms from database.
     */
    suspend fun initialize() = withContext(Dispatchers.IO) {
        if (isInitialized) return@withContext

        Log.d(TAG, "Loading high-risk terms from database...")
        terms = loadTerms()
        isInitialized = true
        Log.d(TAG, "Loaded ${terms.size} high-risk terms")
    }

    /**
     * Load high-risk terms from the database.
     */
    private fun loadTerms(): List<HighRiskTerm> {
        val db = dbHelper.getDatabase()

        val query = "SELECT term, category, severity FROM high_risk_terms"
        val cursor = db.rawQuery(query, null)

        return buildList {
            cursor.use {
                while (it.moveToNext()) {
                    add(
                        HighRiskTerm(
                            term = it.getString(0),
                            category = it.getString(1),
                            severity = it.getString(2)
                        )
                    )
                }
            }
        }
    }

    /**
     * Detect high-risk terms in search results.
     *
     * Scans all result content for matches against the curated term list.
     *
     * @param results List of search results to scan
     * @return List of detected high-risk alerts, sorted by severity (High first)
     */
    fun detectRisks(results: List<SearchResult>): List<HighRiskAlert> {
        if (results.isEmpty() || terms.isEmpty()) return emptyList()

        // Combine all content for efficient scanning
        val contentLower = results.joinToString(" ") { it.content }.lowercase()

        val alerts = mutableListOf<HighRiskAlert>()
        val seenTerms = mutableSetOf<String>()  // Avoid duplicates

        for (term in terms) {
            val termLower = term.term.lowercase()

            // Check if term appears in content
            if (contentLower.contains(termLower) && termLower !in seenTerms) {
                seenTerms.add(termLower)

                val severity = when (term.severity.uppercase()) {
                    "HIGH" -> HighRiskAlert.Severity.HIGH
                    else -> HighRiskAlert.Severity.MEDIUM
                }

                alerts.add(
                    HighRiskAlert(
                        term = term.term,
                        category = term.category,
                        severity = severity
                    )
                )
            }
        }

        // Sort by severity (HIGH first) then alphabetically
        return alerts.sortedWith(
            compareBy<HighRiskAlert> { it.severity }
                .thenBy { it.term }
        )
    }

    /**
     * Check if any high-risk terms require immediate attention.
     *
     * @param alerts List of detected alerts
     * @return true if any alert has HIGH severity
     */
    fun hasHighSeverity(alerts: List<HighRiskAlert>): Boolean {
        return alerts.any { it.severity == HighRiskAlert.Severity.HIGH }
    }

    /**
     * Get the highest severity level from alerts.
     *
     * @param alerts List of detected alerts
     * @return Highest severity, or null if no alerts
     */
    fun getMaxSeverity(alerts: List<HighRiskAlert>): HighRiskAlert.Severity? {
        return alerts.minByOrNull { it.severity }?.severity
    }
}
