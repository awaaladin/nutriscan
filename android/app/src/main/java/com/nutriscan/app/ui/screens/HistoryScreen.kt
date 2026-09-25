package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
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
import com.nutriscan.app.data.model.HistoryItem
import com.nutriscan.app.data.repository.NutriScanRepository

private enum class HistoryFilter { ALL, GOOD, MODERATE, AVOID }

@Composable
fun HistoryScreen(repository: NutriScanRepository) {
    var items by remember { mutableStateOf<List<HistoryItem>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var filter by remember { mutableStateOf(HistoryFilter.ALL) }

    LaunchedEffect(Unit) {
        val result = repository.history()
        isLoading = false
        result.onSuccess { items = it }.onFailure { errorMessage = it.message }
    }

    val filtered = items.filter {
        when (filter) {
            HistoryFilter.ALL -> true
            HistoryFilter.GOOD -> it.label == "Good"
            HistoryFilter.MODERATE -> it.label == "Moderate"
            HistoryFilter.AVOID -> it.label == "Avoid"
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("History", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(8.dp))
        Row {
            HistoryFilter.entries.forEach { option ->
                FilterChip(
                    selected = filter == option,
                    onClick = { filter = option },
                    label = { Text(option.name.lowercase().replaceFirstChar { c -> c.uppercase() }) },
                    modifier = Modifier.padding(end = 8.dp),
                )
            }
        }
        Spacer(Modifier.height(8.dp))
        when {
            isLoading -> CircularProgressIndicator()
            errorMessage != null -> Text(errorMessage ?: "", color = MaterialTheme.colorScheme.error)
            filtered.isEmpty() -> Text("No scans in this category yet.")
            else -> LazyColumn {
                items(filtered) { item ->
                    ListItem(
                        headlineContent = { Text(item.product.name) },
                        supportingContent = { Text("${item.label} · ${item.score}/10 · ${item.scanned_at}") },
                    )
                    HorizontalDivider()
                }
            }
        }
    }
}
