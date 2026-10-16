package com.nutriscan.app.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AddCircle
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.ProductSubmissionRequest
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsAmber
import kotlinx.coroutines.launch

@Composable
fun SubmitProductScreen(
    repository: NutriScanRepository,
    barcode: String,
    onBack: () -> Unit,
    onSubmitted: () -> Unit,
) {
    var name by remember { mutableStateOf("") }
    var brand by remember { mutableStateOf("") }
    var sugar by remember { mutableStateOf("") }
    var sodium by remember { mutableStateOf("") }
    var ingredients by remember { mutableStateOf("") }
    var isSubmitting by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    NsScreenScaffold(title = "Add product", onBack = onBack) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier.size(48.dp).background(NsAmber.copy(alpha = 0.15f), CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(Icons.Rounded.AddCircle, contentDescription = null, tint = NsAmber)
                }
                Spacer(Modifier.width(12.dp))
                Column {
                    Text("We couldn't find this product", style = MaterialTheme.typography.titleMedium)
                    Text("Barcode: $barcode", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Spacer(Modifier.height(16.dp))
            Text(
                "Help us add it for other shoppers — your submission is reviewed before it goes live. " +
                    "Prefer not to type it all in? Go back to the scanner and tap \"Take a photo instead\" " +
                    "to let our AI read the label for you.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(20.dp))
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text("Product name") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = brand,
                onValueChange = { brand = it },
                label = { Text("Brand") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = sugar,
                onValueChange = { sugar = it },
                label = { Text("Sugar (g per 100g)") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = sodium,
                onValueChange = { sodium = it },
                label = { Text("Sodium (mg per 100g)") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = ingredients,
                onValueChange = { ingredients = it },
                label = { Text("Ingredients") },
                modifier = Modifier.fillMaxWidth(),
            )
            AnimatedVisibility(visible = errorMessage != null, enter = fadeIn() + expandVertically(), exit = fadeOut()) {
                Column {
                    Spacer(Modifier.height(8.dp))
                    Text(errorMessage ?: "", color = MaterialTheme.colorScheme.error)
                }
            }
            Spacer(Modifier.height(16.dp))
            NsButton(
                enabled = !isSubmitting && name.isNotBlank(),
                text = if (isSubmitting) "Submitting…" else "Submit product",
                onClick = {
                    isSubmitting = true
                    errorMessage = null
                    scope.launch {
                        val request = ProductSubmissionRequest(
                            barcode = barcode,
                            name = name,
                            brand = brand,
                            nutrition_payload = mapOf(
                                "sugar_g" to sugar.toDoubleOrNull(),
                                "sodium_mg" to sodium.toDoubleOrNull(),
                            ),
                            ingredients_text = ingredients,
                        )
                        val result = repository.submitProduct(request)
                        isSubmitting = false
                        result.onSuccess { onSubmitted() }.onFailure { errorMessage = it.message }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}
