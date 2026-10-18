package com.nutriscan.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.SearchResult
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.HealthLabelChip
import com.nutriscan.app.ui.components.NsScreenScaffold
import kotlinx.coroutines.delay

/**
 * Find a product in our own data set by name, brand, barcode or NAFDAC number, without
 * scanning. Every result says how far its data can be trusted, so the database is both
 * easy to search and honest about what it knows.
 */
@Composable
fun SearchScreen(
    repository: NutriScanRepository,
    onBack: () -> Unit,
    onOpenProduct: (barcode: String) -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<SearchResult>?>(null) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    // Search shortly after the user stops typing, not on every keystroke.
    LaunchedEffect(query) {
        if (query.trim().length < 2) {
            results = null
            error = null
            return@LaunchedEffect
        }
        delay(400)
        loading = true
        repository.searchProducts(query.trim())
            .onSuccess { results = it.results; error = null }
            .onFailure { error = it.message ?: "Couldn't search right now." }
        loading = false
    }

    NsScreenScaffold(title = "Search products", onBack = onBack) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it.take(100) },
                label = { Text("Name, brand, barcode or NAFDAC number") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))
            when {
                error != null -> Text(error ?: "", color = MaterialTheme.colorScheme.error)
                loading && results == null -> CircularProgressIndicator()
                results == null -> Text(
                    "Search the NutriScan database: every product shows how far its data can be trusted.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                results.orEmpty().isEmpty() -> Text(
                    "Nothing found for \"${query.trim()}\". Scan the product to add it.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                else -> LazyColumn {
                    items(results.orEmpty(), key = { it.barcode }) { result ->
                        ListItem(
                            modifier = Modifier.clickable { onOpenProduct(result.barcode) },
                            headlineContent = { Text(result.name, maxLines = 2) },
                            supportingContent = {
                                Column {
                                    result.brand?.takeIf { it.isNotBlank() }?.let {
                                        Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                    Spacer(Modifier.height(2.dp))
                                    TrustBadge(result.trust.level, result.trust.headline)
                                }
                            },
                            trailingContent = {
                                Column(horizontalAlignment = Alignment.End) {
                                    result.label?.let { HealthLabelChip(it) }
                                    Text(result.score?.let { "$it/10" } ?: "—", style = MaterialTheme.typography.labelMedium)
                                }
                            },
                        )
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}
