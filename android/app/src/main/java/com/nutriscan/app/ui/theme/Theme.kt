package com.nutriscan.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val NsGreen = Color(0xFF1B8A5A)
val NsAmber = Color(0xFFE0A62F)
val NsRed = Color(0xFFD64545)
val NsBackground = Color(0xFFF7F8F7)
val NsSurface = Color(0xFFFFFFFF)

private val NutriScanColorScheme = lightColorScheme(
    primary = NsGreen,
    secondary = NsAmber,
    error = NsRed,
    background = NsBackground,
    surface = NsSurface,
)

@Composable
fun NutriScanTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = NutriScanColorScheme,
        content = content,
    )
}
