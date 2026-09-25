package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.ui.MainViewModel
import com.nutriscan.app.ui.ScanUiState

@Composable
fun ProductDetailScreen(viewModel: MainViewModel, onViewAnalysis: () -> Unit) {
    val scanState by viewModel.scanState.collectAsState()
    val result = (scanState as? ScanUiState.Success)?.result

    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        if (result == null) {
            Text("No product loaded.")
        } else {
            Text(result.product.name, style = MaterialTheme.typography.headlineSmall)
            result.product.brand?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
            Spacer(Modifier.height(16.dp))
            Text("Nutrition (per 100g)", style = MaterialTheme.typography.titleMedium)
            NutritionRow("Calories", result.product.calories_kcal, "kcal")
            NutritionRow("Sugar", result.product.sugar_g, "g")
            NutritionRow("Saturated fat", result.product.saturated_fat_g, "g")
            NutritionRow("Sodium", result.product.sodium_mg, "mg")
            NutritionRow("Carbohydrates", result.product.carbohydrates_g, "g")
            NutritionRow("Fiber", result.product.fiber_g, "g")
            NutritionRow("Protein", result.product.protein_g, "g")
            Spacer(Modifier.height(16.dp))
            Text("Ingredients", style = MaterialTheme.typography.titleMedium)
            Text(result.product.ingredients_text?.ifBlank { "Not available" } ?: "Not available")
            if (result.product.additives.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text("Additives: ${result.product.additives.joinToString()}")
            }
            Spacer(Modifier.height(24.dp))
            Button(onClick = onViewAnalysis, modifier = Modifier.fillMaxWidth()) {
                Text("View health analysis")
            }
        }
    }
}

@Composable
private fun NutritionRow(label: String, value: Double?, unit: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(label, modifier = Modifier.weight(1f))
        Text(if (value != null) "$value $unit" else "N/A")
    }
}
