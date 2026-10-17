package com.nutriscan.app.ui.screens

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
import androidx.compose.material3.TextButton
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
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsOutlinedButton
import com.nutriscan.app.ui.theme.NsCream
import com.nutriscan.app.ui.theme.NsEmerald900
import com.nutriscan.app.ui.theme.NsGold300
import kotlinx.coroutines.delay

/**
 * Sits between a scan/photo submission and a result, and always says what is
 * happening or what went wrong -- never an endless generic spinner:
 *  - Loading shows the real current step plus a running seconds counter.
 *  - Success and NeedsPhotos move on automatically (a product that isn't in our
 *    database goes straight to the photo screen, not a dead end).
 *  - Failures stay here with the specific reason and clear next steps.
 */
@Composable
fun AnalyzingScreen(
    viewModel: MainViewModel,
    onSuccess: (barcode: String) -> Unit,
    onNeedsPhotos: (barcode: String?) -> Unit,
    onRetakePhotos: (barcode: String?) -> Unit,
    onManualEntry: (barcode: String) -> Unit,
    onRetry: () -> Unit,
) {
    val scanState by viewModel.scanState.collectAsState()
    var elapsedSeconds by remember { mutableIntStateOf(0) }

    LaunchedEffect(scanState) {
        elapsedSeconds = 0
        while (scanState is ScanUiState.Loading) {
            delay(1000)
            elapsedSeconds++
        }
        when (val state = scanState) {
            is ScanUiState.Success -> onSuccess(state.result.product.barcode)
            is ScanUiState.NeedsPhotos -> onNeedsPhotos(state.barcode)
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
                is ScanUiState.IdentifyFailed -> Message(
                    title = if (state.retake) "Couldn't read the photos" else "Couldn't research this product",
                    body = state.message,
                ) {
                    NsButton(
                        text = if (state.retake) "Retake photos" else "Try again",
                        onClick = { onRetakePhotos(state.barcode) },
                    )
                    Spacer(Modifier.height(8.dp))
                    state.barcode?.takeIf { it.isNotBlank() }?.let { barcode ->
                        TextButton(onClick = { onManualEntry(barcode) }) {
                            Text("Enter the details manually instead", color = NsGold300)
                        }
                    }
                    TextButton(onClick = onRetry) { Text("Scan something else", color = NsGold300) }
                }
                is ScanUiState.Error -> Message(title = "Couldn't complete this scan", body = state.message) {
                    NsOutlinedButton(text = "Try again", onClick = onRetry)
                }
                is ScanUiState.NonFood -> Message(
                    title = "Not a packaged food",
                    body = state.message,
                    subtitle = state.productName,
                ) {
                    NsOutlinedButton(text = "Scan something else", onClick = onRetry)
                }
                is ScanUiState.Offline -> Message(
                    title = "You're offline",
                    body = "Showing the last result saved for this product.",
                ) {
                    Text(state.cached.productName, style = MaterialTheme.typography.titleMedium, color = NsCream)
                    Spacer(Modifier.height(8.dp))
                    HealthLabelChip(state.cached.label)
                    Spacer(Modifier.height(8.dp))
                    Text("${state.cached.score}/10", style = MaterialTheme.typography.headlineSmall, color = NsGold300)
                    Spacer(Modifier.height(24.dp))
                    NsOutlinedButton(text = "Scan again", onClick = onRetry)
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
                    Text(
                        (state as? ScanUiState.Loading)?.message ?: "Working…",
                        style = MaterialTheme.typography.titleMedium,
                        color = NsCream,
                        textAlign = TextAlign.Center,
                    )
                    Spacer(Modifier.height(12.dp))
                    Text(
                        "${elapsedSeconds}s",
                        style = MaterialTheme.typography.bodyMedium,
                        color = NsCream.copy(alpha = 0.6f),
                    )
                }
            }
        }
    }
}

@Composable
private fun Message(
    title: String,
    body: String,
    subtitle: String? = null,
    actions: @Composable () -> Unit,
) {
    AnimatedVisibility(
        visible = true,
        enter = fadeIn(tween(350)) + slideInVertically(tween(350)) { it / 4 },
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(title, style = MaterialTheme.typography.titleLarge, color = NsCream, textAlign = TextAlign.Center)
            subtitle?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, style = MaterialTheme.typography.titleMedium, color = NsGold300)
            }
            Spacer(Modifier.height(12.dp))
            Text(body, color = NsCream.copy(alpha = 0.85f), textAlign = TextAlign.Center)
            Spacer(Modifier.height(24.dp))
            actions()
        }
    }
}
