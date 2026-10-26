package com.choropia.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

private val LightColors = lightColorScheme(
    primary = LightTokens.primary,
    onPrimary = LightTokens.onPrimary,
    primaryContainer = LightTokens.container,
    onPrimaryContainer = LightTokens.onSurface,
    secondary = LightTokens.secondary,
    onSecondary = Color.White,
    secondaryContainer = LightTokens.secondaryContainer,
    onSecondaryContainer = LightTokens.onSecondaryContainer,
    background = LightTokens.surface,
    onBackground = LightTokens.onSurface,
    surface = LightTokens.surface,
    onSurface = LightTokens.onSurface,
    surfaceVariant = LightTokens.container,
    onSurfaceVariant = LightTokens.onSurfaceVariant,
    surfaceContainerLowest = LightTokens.surfaceBright,
    surfaceContainerLow = LightTokens.containerLow,
    surfaceContainer = LightTokens.container,
    surfaceContainerHigh = LightTokens.container,
    surfaceContainerHighest = LightTokens.outlineVariant,
    outline = LightTokens.outline,
    outlineVariant = LightTokens.outlineVariant,
    error = LightTokens.error,
    errorContainer = LightTokens.errorContainer,
)

private val DarkColors = darkColorScheme(
    primary = DarkTokens.primary,
    onPrimary = DarkTokens.onPrimary,
    primaryContainer = DarkTokens.container,
    onPrimaryContainer = DarkTokens.onSurface,
    secondary = DarkTokens.secondary,
    onSecondary = DarkTokens.onPrimary,
    secondaryContainer = DarkTokens.secondaryContainer,
    onSecondaryContainer = DarkTokens.onSecondaryContainer,
    background = DarkTokens.surface,
    onBackground = DarkTokens.onSurface,
    surface = DarkTokens.surface,
    onSurface = DarkTokens.onSurface,
    surfaceVariant = DarkTokens.container,
    onSurfaceVariant = DarkTokens.onSurfaceVariant,
    surfaceContainerLowest = DarkTokens.surfaceBright,
    surfaceContainerLow = DarkTokens.containerLow,
    surfaceContainer = DarkTokens.container,
    surfaceContainerHigh = DarkTokens.container,
    surfaceContainerHighest = DarkTokens.outlineVariant,
    outline = DarkTokens.outline,
    outlineVariant = DarkTokens.outlineVariant,
    error = DarkTokens.error,
    errorContainer = DarkTokens.errorContainer,
)

// Softer than the printed spec on purpose: matches the web app's rounder, social feel.
private val ChoropiaShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(14.dp),
    large = RoundedCornerShape(20.dp),
    extraLarge = RoundedCornerShape(28.dp),
)

/** Whether the active theme is dark; the brand logo uses it to pick navy vs white artwork. */
val LocalIsDark = staticCompositionLocalOf { false }

@Composable
fun ChoropiaTheme(themeMode: String = "system", content: @Composable () -> Unit) {
    val dark = when (themeMode) {
        "dark" -> true
        "light" -> false
        else -> isSystemInDarkTheme()
    }
    val colors: ColorScheme = if (dark) DarkColors else LightColors
    CompositionLocalProvider(LocalIsDark provides dark) {
        MaterialTheme(colorScheme = colors, typography = ChoropiaTypography, shapes = ChoropiaShapes, content = content)
    }
}
