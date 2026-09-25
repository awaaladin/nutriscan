package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.ProductSubmissionRequest
import com.nutriscan.app.data.repository.NutriScanRepository
import kotlinx.coroutines.launch

@Composable
fun SubmitProductScreen(
    repository: NutriScanRepository,
    barcode: String,
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

    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Text("We couldn't find this product", style = MaterialTheme.typography.headlineSmall)
        Text("Barcode: $barcode", style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(16.dp))
        Text("Help us add it for other Nigerian shoppers.")
        Spacer(Modifier.height(16.dp))
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
        errorMessage?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(16.dp))
        Button(
            enabled = !isSubmitting && name.isNotBlank(),
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
        ) {
            Text(if (isSubmitting) "Submitting..." else "Submit product")
        }
    }
}
