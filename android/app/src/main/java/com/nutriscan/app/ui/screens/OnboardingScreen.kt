package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.selection.selectable
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

private val goals = listOf(
    "general_health" to "General health",
    "diabetes" to "Diabetes management",
    "weight_loss" to "Weight loss",
    "hypertension" to "Hypertension management",
)

@Composable
fun OnboardingScreen(onContinue: (goal: String) -> Unit) {
    var selected by remember { mutableStateOf(goals.first().first) }

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("NutriScan", style = MaterialTheme.typography.headlineLarge)
        Spacer(Modifier.height(8.dp))
        Text("Scan food. Know what you eat.", style = MaterialTheme.typography.bodyLarge)
        Spacer(Modifier.height(32.dp))
        Text("What's your main goal?", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(12.dp))
        goals.forEach { (key, label) ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .selectable(selected = selected == key, onClick = { selected = key })
                    .padding(vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = selected == key, onClick = { selected = key })
                Spacer(Modifier.width(8.dp))
                Text(label)
            }
        }
        Spacer(Modifier.height(24.dp))
        Button(onClick = { onContinue(selected) }, modifier = Modifier.fillMaxWidth()) {
            Text("Get started")
        }
    }
}
