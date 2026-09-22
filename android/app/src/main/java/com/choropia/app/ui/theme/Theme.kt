package com.choropia.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val ChoropiaGreen = Color(0xFF0F766E)
val ChoropiaGreenDark = Color(0xFF0B544E)

private val LightColors = lightColorScheme(
    primary = ChoropiaGreen,
    secondary = ChoropiaGreenDark,
)

private val DarkColors = darkColorScheme(
    primary = ChoropiaGreen,
    secondary = ChoropiaGreenDark,
)

@Composable
fun ChoropiaTheme(content: @Composable () -> Unit) {
    val colors = if (isSystemInDarkTheme()) DarkColors else LightColors
    MaterialTheme(colorScheme = colors, content = content)
}
