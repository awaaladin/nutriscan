package com.nutriscan.app.ui.components

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.nutriscan.app.R

private val ScanGreen = Color(0xFF8CC63F)

/** The NutriScan badge (see branding/logo.svg). A vector, so it stays sharp at any size. */
@Composable
fun LogoMark(size: Dp, modifier: Modifier = Modifier) {
    Image(
        painter = painterResource(R.drawable.ic_logo),
        contentDescription = "NutriScan logo",
        modifier = modifier.size(size),
    )
}

/** "Nutri" in the surrounding text colour and "Scan" in the brand green, as in the logo. */
@Composable
fun NutriScanWordmark(
    fontSize: TextUnit = 22.sp,
    nutriColor: Color = MaterialTheme.colorScheme.onBackground,
    modifier: Modifier = Modifier,
) {
    Text(
        text = buildAnnotatedString {
            withStyle(SpanStyle(color = nutriColor, fontWeight = FontWeight.ExtraBold)) { append("Nutri") }
            withStyle(SpanStyle(color = ScanGreen, fontWeight = FontWeight.ExtraBold)) { append("Scan") }
        },
        fontSize = fontSize,
        modifier = modifier,
    )
}

/** Badge + wordmark side by side, e.g. for app bars. */
@Composable
fun LogoLockup(markSize: Dp = 30.dp, fontSize: TextUnit = 22.sp, nutriColor: Color = MaterialTheme.colorScheme.onBackground) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        LogoMark(markSize)
        Spacer(Modifier.width(10.dp))
        NutriScanWordmark(fontSize = fontSize, nutriColor = nutriColor)
    }
}
