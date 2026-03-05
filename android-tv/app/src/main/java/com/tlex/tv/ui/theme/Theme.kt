package com.tlex.tv.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val TlexColorScheme = darkColorScheme(
    primary = TlexGold,
    onPrimary = BackgroundPrimary,
    primaryContainer = SurfaceVariant,
    onPrimaryContainer = TextPrimary,
    secondary = TextSecondary,
    onSecondary = TextPrimary,
    background = BackgroundPrimary,
    onBackground = TextPrimary,
    surface = BackgroundSecondary,
    onSurface = TextPrimary,
    surfaceVariant = SurfaceVariant,
    onSurfaceVariant = TextSecondary,
    error = ErrorRed,
    onError = TextPrimary
)

@Composable
fun TlexTVTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = TlexColorScheme,
        typography = TlexTypography,
        content = content
    )
}
