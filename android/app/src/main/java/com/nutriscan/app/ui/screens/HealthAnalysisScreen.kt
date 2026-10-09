package com.nutriscan.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.ui.MainViewModel
import com.nutriscan.app.ui.ScanUiState
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsAmber
import com.nutriscan.app.ui.theme.NsEmerald500
import com.nutriscan.app.ui.theme.NsRed

@Composable
fun HealthAnalysisScreen(viewModel: MainViewModel, onBack: () -> Unit) {
    val scanState by viewModel.scanState.collectAsState()
    // Only reachable via a Success outcome, which the repository only emits for
    // food items, so score/label/diabetic_risk/explanation are always present here
    // even though ScanResponse types them nullable for the non-food/medicine case.
    val result = (scanState as? ScanUiState.Success)?.result
    val score = result?.score
    val label = result?.label
    val diabeticRisk = result?.diabetic_risk
    val explanation = result?.explanation

    NsScreenScaffold(title = "Health analysis", onBack = onBack) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp)) {
            if (result == null || score == null || label == null) {
                Text("No analysis available.")
            } else {
                Text(result.product.name, style = MaterialTheme.typography.headlineSmall)
                Spacer(Modifier.height(16.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    TrafficLight(label)
                    Spacer(Modifier.width(12.dp))
                    Column {
                        Text("$score/10", style = MaterialTheme.typography.headlineMedium)
                        Text(label, style = MaterialTheme.typography.titleMedium)
                    }
                }
                if (result.is_estimated) {
                    Spacer(Modifier.height(12.dp))
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(MaterialTheme.colorScheme.secondaryContainer, shape = androidx.compose.foundation.shape.RoundedCornerShape(12.dp))
                            .padding(12.dp),
                    ) {
                        Text(
                            "Estimated from a photo, not a verified nutrition label match -- double-check against the package.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSecondaryContainer,
                        )
                    }
                }
                if (result.insufficient_data) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Some nutrition data was missing for this product; score may be incomplete.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                Spacer(Modifier.height(16.dp))
                Text("Diabetic risk: ${diabeticRisk.orEmpty()}", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(16.dp))
                if (result.flags.isNotEmpty()) {
                    Text("Flags", style = MaterialTheme.typography.titleMedium)
                    result.flags.forEach { flag -> Text("• ${flag.replace('_', ' ')}") }
                    Spacer(Modifier.height(16.dp))
                }
                Text("Why", style = MaterialTheme.typography.titleMedium)
                Text(explanation.orEmpty())
                Spacer(Modifier.height(8.dp))
                Text(
                    "This is educational information, not medical advice.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(24.dp))
                NsButton(text = "Back to home", onClick = onBack, modifier = Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
private fun TrafficLight(label: String) {
    val color = when (label) {
        "Good" -> NsEmerald500
        "Moderate" -> NsAmber
        else -> NsRed
    }
    Box(modifier = Modifier.size(48.dp).background(color, shape = CircleShape))
}
