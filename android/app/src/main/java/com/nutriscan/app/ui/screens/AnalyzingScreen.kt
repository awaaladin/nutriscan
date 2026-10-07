package com.nutriscan.app.ui.screens

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.QrCodeScanner
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.nutriscan.app.ui.MainViewModel
import com.nutriscan.app.ui.ScanUiState
import com.nutriscan.app.ui.components.AnimatedGradientBackground
import com.nutriscan.app.ui.components.HealthLabelChip
import com.nutriscan.app.ui.components.NsOutlinedButton
import com.nutriscan.app.ui.theme.NsCream
import com.nutriscan.app.ui.theme.NsEmerald900
import com.nutriscan.app.ui.theme.NsGold300
import kotlinx.coroutines.delay

private val statusPhrases = listOf(
    "Reading barcode…",
    "Fetching product data…",
    "Applying WHO thresholds…",
    "Checking diabetic risk…",
)

/**
 * Sits between a captured barcode and a result. Success/NotFound auto-advance
 * once the network call resolves. Error and Offline are terminal states that
 * stay on this screen — Error so the user can read what happened before
 * retrying, Offline because the cached record doesn't carry full nutrition
 * data, so there's nowhere richer to send them.
 */
@Composable
fun AnalyzingScreen(
    viewModel: MainViewModel,
    onSuccess: (barcode: String) -> Unit,
    onNotFound: (barcode: String) -> Unit,
    onRetry: () -> Unit,
) {
    val scanState by viewModel.scanState.collectAsState()
    var statusIndex by remember { mutableIntStateOf(0) }

    LaunchedEffect(scanState) {
        while (scanState is ScanUiState.Loading) {
            delay(900)
            statusIndex = (statusIndex + 1) % statusPhrases.size
        }
        when (val state = scanState) {
            is ScanUiState.Success -> onSuccess(state.result.product.barcode)
            is ScanUiState.NotFound -> onNotFound(state.barcode)
            else -> Unit
        }
    }

    val rotation = rememberInfiniteTransition(label = "analyzeRotate")
    val angle by rotation.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(1600, easing = LinearEasing)),
        label = "angle",
    )

    AnimatedGradientBackground(colors = listOf(NsEmerald900, Color(0xFF123D2C), NsEmerald900)) {
        Column(
            modifier = Modifier.fillMaxSize().padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            when (val state = scanState) {
                is ScanUiState.Error -> {
                    AnimatedVisibility(
                        visible = true,
                        enter = fadeIn(tween(350)) + slideInVertically(tween(350)) { it / 4 },
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("Couldn't complete this scan", style = MaterialTheme.typography.titleLarge, color = NsCream)
                            Spacer(Modifier.height(12.dp))
                            Text(state.message, color = NsCream.copy(alpha = 0.8f), textAlign = TextAlign.Center)
                            Spacer(Modifier.height(24.dp))
                            NsOutlinedButton(text = "Try again", onClick = onRetry)
                        }
                    }
                }
                is ScanUiState.NonFood -> {
                    AnimatedVisibility(
                        visible = true,
                        enter = fadeIn(tween(350)) + slideInVertically(tween(350)) { it / 4 },
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("Not a packaged food", style = MaterialTheme.typography.titleLarge, color = NsCream)
                            Spacer(Modifier.height(8.dp))
                            Text(state.productName, style = MaterialTheme.typography.titleMedium, color = NsGold300)
                            Spacer(Modifier.height(12.dp))
                            Text(state.message, color = NsCream.copy(alpha = 0.8f), textAlign = TextAlign.Center)
                            Spacer(Modifier.height(24.dp))
                            NsOutlinedButton(text = "Scan something else", onClick = onRetry)
                        }
                    }
                }
                is ScanUiState.Offline -> {
                    AnimatedVisibility(
                        visible = true,
                        enter = fadeIn(tween(350)) + slideInVertically(tween(350)) { it / 4 },
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("You're offline", style = MaterialTheme.typography.titleLarge, color = NsCream)
                            Spacer(Modifier.height(8.dp))
                            Text(
                                "Showing the last result saved for this product.",
                                color = NsCream.copy(alpha = 0.75f),
                                textAlign = TextAlign.Center,
                            )
                            Spacer(Modifier.height(20.dp))
                            Text(state.cached.productName, style = MaterialTheme.typography.titleMedium, color = NsCream)
                            Spacer(Modifier.height(8.dp))
                            HealthLabelChip(state.cached.label)
                            Spacer(Modifier.height(8.dp))
                            Text("${state.cached.score}/10", style = MaterialTheme.typography.headlineSmall, color = NsGold300)
                            Spacer(Modifier.height(24.dp))
                            NsOutlinedButton(text = "Scan again", onClick = onRetry)
                        }
                    }
                }
                else -> {
                    Box(contentAlignment = Alignment.Center, modifier = Modifier.size(140.dp)) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(140.dp).rotate(angle),
                            color = NsGold300,
                            strokeWidth = 3.dp,
                            trackColor = NsCream.copy(alpha = 0.12f),
                        )
                        Icon(
                            Icons.Rounded.QrCodeScanner,
                            contentDescription = null,
                            tint = NsGold300,
                            modifier = Modifier.size(52.dp).alpha(0.9f),
                        )
                    }
                    Spacer(Modifier.height(40.dp))
                    AnimatedContent(targetState = statusIndex, label = "statusText") { index ->
                        Text(
                            statusPhrases[index],
                            style = MaterialTheme.typography.titleMedium,
                            color = NsCream,
                            textAlign = TextAlign.Center,
                        )
                    }
                }
            }
        }
    }
}
