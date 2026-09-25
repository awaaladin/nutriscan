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
import androidx.compose.material3.Button
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
import com.nutriscan.app.ui.theme.NsAmber
import com.nutriscan.app.ui.theme.NsGreen
import com.nutriscan.app.ui.theme.NsRed

@Composable
fun HealthAnalysisScreen(viewModel: MainViewModel, onBack: () -> Unit) {
    val scanState by viewModel.scanState.collectAsState()
    val result = (scanState as? ScanUiState.Success)?.result

    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        if (result == null) {
            Text("No analysis available.")
        } else {
            Text(result.product.name, style = MaterialTheme.typography.headlineSmall)
            Spacer(Modifier.height(16.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                TrafficLight(result.label)
                Spacer(Modifier.width(12.dp))
                Column {
                    Text("${result.score}/10", style = MaterialTheme.typography.headlineMedium)
                    Text(result.label, style = MaterialTheme.typography.titleMedium)
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
            Text("Diabetic risk: ${result.diabetic_risk}", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(16.dp))
            if (result.flags.isNotEmpty()) {
                Text("Flags", style = MaterialTheme.typography.titleMedium)
                result.flags.forEach { flag -> Text("• ${flag.replace('_', ' ')}") }
                Spacer(Modifier.height(16.dp))
            }
            Text("Why", style = MaterialTheme.typography.titleMedium)
            Text(result.explanation)
            Spacer(Modifier.height(8.dp))
            Text(
                "This is educational information, not medical advice.",
                style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(24.dp))
            Button(onClick = onBack, modifier = Modifier.fillMaxWidth()) {
                Text("Back to home")
            }
        }
    }
}

@Composable
private fun TrafficLight(label: String) {
    val color = when (label) {
        "Good" -> NsGreen
        "Moderate" -> NsAmber
        else -> NsRed
    }
    Box(modifier = Modifier.size(48.dp).background(color, shape = CircleShape))
}
