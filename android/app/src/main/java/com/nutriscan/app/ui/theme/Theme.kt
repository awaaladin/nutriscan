package com.nutriscan.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = NsEmerald700,
    onPrimary = NsWhite,
    primaryContainer = NsEmerald200,
    onPrimaryContainer = NsEmerald900,
    secondary = NsGold500,
    onSecondary = NsWhite,
    secondaryContainer = NsGold300,
    onSecondaryContainer = NsCharcoal900,
    error = NsRed,
    onError = NsWhite,
    background = NsCream,
    onBackground = NsCharcoal900,
    surface = NsWhite,
    onSurface = NsCharcoal900,
    surfaceVariant = NsCreamDim,
    onSurfaceVariant = NsCharcoal700,
    outline = NsCharcoal400,
)

private val DarkColors = darkColorScheme(
    primary = NsEmerald500,
    onPrimary = NsCharcoal900,
    primaryContainer = NsEmerald700,
    onPrimaryContainer = NsEmerald200,
    secondary = NsGold300,
    onSecondary = NsCharcoal900,
    secondaryContainer = NsGold500,
    onSecondaryContainer = NsCharcoal900,
    error = NsRedLight,
    onError = NsCharcoal900,
    background = NsSurfaceDark,
    onBackground = NsCream,
    surface = NsSurfaceDarkElevated,
    onSurface = NsCream,
    surfaceVariant = NsSurfaceDarkElevated,
    onSurfaceVariant = NsCharcoal400,
    outline = NsCharcoal400,
)

@Composable
fun NutriScanTheme(
    useDarkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (useDarkTheme) DarkColors else LightColors,
        typography = NutriScanTypography,
        shapes = NutriScanShapes,
        content = content,
    )
}
