package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.nutriscan.app.ui.MainViewModel
import com.nutriscan.app.ui.ScanUiState
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsScreenScaffold

private data class Field(val key: String, val label: String, val hint: String? = null)

private val fields = listOf(
    Field("sugar_g", "Sugar (g)"),
    Field("saturated_fat_g", "Saturated fat (g)"),
    Field("sodium_mg", "Sodium (mg)", "Label shows salt, not sodium? Sodium in mg = salt in g × 400."),
    Field("calories_kcal", "Calories (kcal)"),
    Field("carbohydrates_g", "Carbohydrates (g)"),
    Field("fiber_g", "Fibre (g)"),
    Field("protein_g", "Protein (g)"),
)

/**
 * Type in a product's missing nutrition values straight from its label. Labels
 * usually list values per serving, so a switch converts them to per 100g on the
 * server. Only blanks are filled and impossible numbers are rejected there, so
 * a typo can't silently change a score -- the screen just reports why.
 */
@Composable
fun NutritionEntryScreen(
    viewModel: MainViewModel,
    barcode: String,
    onBack: () -> Unit,
    onSubmit: () -> Unit,
) {
    val values = remember { mutableStateOf(fields.associate { it.key to "" }) }
    var perServing by remember { mutableStateOf(false) }
    var servingSize by remember { mutableStateOf("") }
    var ingredients by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    val lastFailure = (viewModel.scanState.value as? ScanUiState.IdentifyFailed)?.message

    NsScreenScaffold(title = "Add nutrition values", onBack = onBack) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp, vertical = 16.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            lastFailure?.let {
                Text("The last attempt didn't work: $it", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(8.dp))
            }
            Text(
                "Copy the numbers from the nutrition table on the pack. Fill in what you can see -- " +
                    "leave the rest blank. Only missing values are added; nothing already on file is changed.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("The label shows values per serving", style = MaterialTheme.typography.titleSmall)
                    Text(
                        if (perServing) "We'll convert them to per 100 g." else "Values are already per 100 g (or 100 ml).",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(checked = perServing, onCheckedChange = { perServing = it })
            }
            if (perServing) {
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = servingSize,
                    onValueChange = { servingSize = it },
                    label = { Text("Serving size (g or ml)") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            Spacer(Modifier.height(8.dp))
            fields.forEach { field ->
                OutlinedTextField(
                    value = values.value.getValue(field.key),
                    onValueChange = { values.value = values.value + (field.key to it) },
                    label = { Text(field.label) },
                    supportingText = field.hint?.let { hint -> { Text(hint) } },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                )
            }
            OutlinedTextField(
                value = ingredients,
                onValueChange = { ingredients = it.take(3000) },
                label = { Text("Ingredients (optional, if not already listed)") },
                minLines = 2,
                modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
            )
            error?.let {
                Spacer(Modifier.height(4.dp))
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(12.dp))
            NsButton(
                text = "Add values and score it",
                onClick = {
                    val typed = values.value.filterValues { it.isNotBlank() }
                    val bad = typed.entries.firstOrNull { it.value.replace(',', '.').toDoubleOrNull() == null }
                    when {
                        typed.isEmpty() && ingredients.isBlank() -> error = "Enter at least one value from the label."
                        bad != null -> error = "\"${bad.value}\" isn't a number. Use digits only, e.g. 12.5."
                        perServing && servingSize.replace(',', '.').toDoubleOrNull() == null ->
                            error = "Enter the serving size in grams or ml to convert per-serving values."
                        else -> {
                            error = null
                            val body = typed.mapValues { it.value.replace(',', '.') }.toMutableMap()
                            if (ingredients.isNotBlank()) body["ingredients_text"] = ingredients.trim()
                            if (perServing) {
                                body["per_serving"] = "true"
                                body["serving_size_g"] = servingSize.replace(',', '.')
                            }
                            viewModel.completeWithValues(barcode, body)
                            onSubmit()
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(24.dp))
        }
    }
}
