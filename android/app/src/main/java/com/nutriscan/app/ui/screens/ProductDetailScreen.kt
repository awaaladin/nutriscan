package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.ui.MainViewModel
import com.nutriscan.app.ui.ScanUiState
import com.nutriscan.app.ui.components.IntegrityCard
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsOutlinedButton
import com.nutriscan.app.ui.components.NsScreenScaffold

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ProductDetailScreen(
    viewModel: MainViewModel,
    onBack: () -> Unit,
    onViewAnalysis: () -> Unit,
    onOpenReports: (barcode: String) -> Unit,
) {
    val scanState by viewModel.scanState.collectAsState()
    val result = (scanState as? ScanUiState.Success)?.result

    NsScreenScaffold(title = "Product", onBack = onBack) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp).verticalScroll(rememberScrollState())) {
            if (result == null) {
                Text("No product loaded.")
            } else {
                Text(result.product.name, style = MaterialTheme.typography.headlineSmall)
                result.product.brand?.let {
                    Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.height(16.dp))
                result.product.integrity?.let { IntegrityCard(it) }
                if (result.is_estimated) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Nutrition values were read from a photo and may be inaccurate.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(Modifier.height(8.dp))
                NsOutlinedButton(
                    text = "Community reports",
                    onClick = { onOpenReports(result.product.barcode) },
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(16.dp))
                Text("Nutrition (per 100g)", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                Card(shape = RoundedCornerShape(16.dp)) {
                    Column(modifier = Modifier.padding(horizontal = 16.dp)) {
                        NutritionRow("Calories", result.product.calories_kcal, "kcal")
                        HorizontalDivider()
                        NutritionRow("Sugar", result.product.sugar_g, "g")
                        HorizontalDivider()
                        NutritionRow("Saturated fat", result.product.saturated_fat_g, "g")
                        HorizontalDivider()
                        NutritionRow("Sodium", result.product.sodium_mg, "mg")
                        HorizontalDivider()
                        NutritionRow("Carbohydrates", result.product.carbohydrates_g, "g")
                        HorizontalDivider()
                        NutritionRow("Fiber", result.product.fiber_g, "g")
                        HorizontalDivider()
                        NutritionRow("Protein", result.product.protein_g, "g")
                    }
                }
                Spacer(Modifier.height(20.dp))
                Text("Ingredients", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                Card(shape = RoundedCornerShape(16.dp)) {
                    Text(
                        result.product.ingredients_text?.ifBlank { "Not available" } ?: "Not available",
                        modifier = Modifier.padding(16.dp),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                if (result.product.additives.isNotEmpty()) {
                    Spacer(Modifier.height(16.dp))
                    Text("Additives", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(8.dp))
                    FlowRow {
                        result.product.additives.forEach { additive ->
                            AssistChip(
                                onClick = {},
                                label = { Text(additive) },
                                modifier = Modifier.padding(end = 8.dp, bottom = 8.dp),
                            )
                        }
                    }
                }
                Spacer(Modifier.height(24.dp))
                NsButton(text = "View health analysis", onClick = onViewAnalysis, modifier = Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
private fun NutritionRow(label: String, value: Double?, unit: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp)) {
        Text(label, modifier = Modifier.weight(1f))
        Text(if (value != null) "$value $unit" else "N/A", style = MaterialTheme.typography.titleSmall)
    }
}
