package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.ProInsights
import com.nutriscan.app.data.repository.NutriScanRepository

@Composable
fun ProInsightsScreen(repository: NutriScanRepository) {
    var insights by remember { mutableStateOf<ProInsights?>(null) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var isLoading by remember { mutableStateOf(true) }

    LaunchedEffect(Unit) {
        val result = repository.proInsights()
        isLoading = false
        result.onSuccess { insights = it }.onFailure { errorMessage = it.message }
    }

    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Text("Pro insights", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(16.dp))
        when {
            isLoading -> CircularProgressIndicator()
            errorMessage != null -> Text(errorMessage ?: "", color = MaterialTheme.colorScheme.error)
            insights != null -> {
                val data = insights!!
                Text("Patterns", style = MaterialTheme.typography.titleMedium)
                if (data.patterns.isEmpty()) {
                    Text("Not enough scans yet to detect patterns.")
                } else {
                    data.patterns.forEach { Text("• $it") }
                }
                Spacer(Modifier.height(16.dp))
                Text("Foods to avoid", style = MaterialTheme.typography.titleMedium)
                if (data.avoid_list.isEmpty()) {
                    Text("Nothing flagged for your profile yet.")
                } else {
                    LazyColumn {
                        items(data.avoid_list) { product ->
                            ListItem(headlineContent = { Text(product.name) })
                        }
                    }
                }
            }
        }
    }
}
