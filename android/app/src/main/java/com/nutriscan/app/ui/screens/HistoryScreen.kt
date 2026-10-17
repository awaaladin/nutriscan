package com.nutriscan.app.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.History
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.HistoryItem
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.HealthLabelChip
import com.nutriscan.app.ui.components.NsOutlinedButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.components.tierColor

private enum class HistoryFilter { ALL, GOOD, MODERATE, AVOID }

@Composable
fun HistoryScreen(repository: NutriScanRepository, onBack: () -> Unit, onOpenScan: (HistoryItem) -> Unit) {
    var items by remember { mutableStateOf<List<HistoryItem>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var filter by remember { mutableStateOf(HistoryFilter.ALL) }
    var retryTick by remember { mutableIntStateOf(0) }

    LaunchedEffect(retryTick) {
        isLoading = true
        errorMessage = null
        val result = repository.history()
        isLoading = false
        result.onSuccess { items = it }.onFailure { errorMessage = it.message ?: "Couldn't load your history." }
    }

    val filtered = items.filter {
        when (filter) {
            HistoryFilter.ALL -> true
            HistoryFilter.GOOD -> it.label == "Good"
            HistoryFilter.MODERATE -> it.label == "Moderate"
            HistoryFilter.AVOID -> it.label == "Avoid"
        }
    }

    NsScreenScaffold(title = "History", onBack = onBack) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
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
            Spacer(Modifier.height(16.dp))
            when {
                isLoading -> Column(
                    modifier = Modifier.fillMaxWidth().padding(top = 48.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    CircularProgressIndicator()
                    Spacer(Modifier.height(12.dp))
                    Text("Loading your history…", style = MaterialTheme.typography.bodyMedium)
                }
                errorMessage != null -> AnimatedVisibility(visible = true, enter = fadeIn(), exit = fadeOut()) {
                    Column(
                        modifier = Modifier.fillMaxWidth().padding(top = 32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(errorMessage ?: "", color = MaterialTheme.colorScheme.error)
                        Spacer(Modifier.height(16.dp))
                        NsOutlinedButton(text = "Try again", onClick = { retryTick++ })
                    }
                }
                filtered.isEmpty() -> Column(
                    modifier = Modifier.fillMaxWidth().padding(top = 48.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Icon(
                        Icons.Outlined.History,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.outline,
                        modifier = Modifier.height(48.dp),
                    )
                    Spacer(Modifier.height(12.dp))
                    Text("No scans in this category yet.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                else -> LazyColumn {
                    items(filtered) { item ->
                        ListItem(
                            modifier = Modifier.clickable { onOpenScan(item) },
                            overlineContent = { Text(item.scanned_at.take(10), style = MaterialTheme.typography.labelSmall) },
                            headlineContent = { Text(item.product.name) },
                            supportingContent = {
                                Column {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        HealthLabelChip(item.label)
                                        item.product.integrity?.let {
                                            Text(
                                                "  ·  ${it.headline}",
                                                style = MaterialTheme.typography.labelMedium,
                                                color = tierColor(it.tier),
                                            )
                                        }
                                    }
                                    item.product.brand?.takeIf { b -> b.isNotBlank() }?.let { b ->
                                        Text(b, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                            },
                            trailingContent = { Text("${item.score}/10", style = MaterialTheme.typography.titleMedium) },
                        )
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}
