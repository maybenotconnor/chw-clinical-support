package org.who.chw.clinical.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

// WHO-inspired color scheme
private val LightBlue = Color(0xFF1976D2)
private val DarkBlue = Color(0xFF0D47A1)
private val LightBlueContainer = Color(0xFFBBDEFB)
private val Orange = Color(0xFFFF5722)
private val White = Color(0xFFFFFFFF)
private val LightGray = Color(0xFFF5F5F5)
private val DarkGray = Color(0xFF424242)

private val LightColorScheme = lightColorScheme(
    primary = LightBlue,
    onPrimary = White,
    primaryContainer = LightBlueContainer,
    onPrimaryContainer = DarkBlue,
    secondary = DarkBlue,
    onSecondary = White,
    tertiary = Orange,
    onTertiary = White,
    background = LightGray,
    onBackground = DarkGray,
    surface = White,
    onSurface = DarkGray,
    error = Color(0xFFB00020),
    onError = White,
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002)
)

private val DarkColorScheme = darkColorScheme(
    primary = Color(0xFF90CAF9),
    onPrimary = Color(0xFF003258),
    primaryContainer = Color(0xFF004880),
    onPrimaryContainer = Color(0xFFD1E4FF),
    secondary = Color(0xFF90CAF9),
    onSecondary = Color(0xFF003258),
    tertiary = Color(0xFFFFAB91),
    onTertiary = Color(0xFF5F1600),
    background = Color(0xFF1C1B1F),
    onBackground = Color(0xFFE6E1E5),
    surface = Color(0xFF1C1B1F),
    onSurface = Color(0xFFE6E1E5),
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6)
)

@Composable
fun CHWClinicalTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography(),
        content = content
    )
}
