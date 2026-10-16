package com.nutriscan.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
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
import com.nutriscan.app.data.model.AlertItem
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.components.tierColor

/** Products with credible fake reports, worst first. A ranked list rather than
 * a social feed: each row opens that product's reports, where people say where
 * they bought it. */
@Composable
fun AlertsScreen(
    repository: NutriScanRepository,
    onBack: () -> Unit,
    onOpenProduct: (barcode: String) -> Unit,
) {
    var alerts by remember { mutableStateOf<List<AlertItem>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        repository.alerts().onSuccess { alerts = it }.onFailure { error = it.message }
    }

    NsScreenScaffold(title = "Fake product alerts", onBack = onBack) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 24.dp)) {
            val list = alerts
            when {
                error != null -> Text(error ?: "", color = MaterialTheme.colorScheme.error)
                list == null -> CircularProgressIndicator()
                list.isEmpty() -> Text(
                    "No products have been reported as fake recently.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    item {
                        Text(
                            "Reported by users in the last 60 days. Reports can be wrong -- tap a product to see the evidence.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(4.dp))
                    }
                    items(list, key = { it.barcode }) { alert ->
                        Card(
                            shape = RoundedCornerShape(16.dp),
                            modifier = Modifier.fillMaxWidth().clickable { onOpenProduct(alert.barcode) },
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text(alert.name, style = MaterialTheme.typography.titleMedium)
                                alert.brand?.takeIf { it.isNotBlank() }?.let {
                                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                Spacer(Modifier.height(6.dp))
                                Text(
                                    "${alert.headline} · ${alert.fake_votes} report(s)",
                                    style = MaterialTheme.typography.labelLarge,
                                    color = tierColor(alert.tier),
                                )
                                if (alert.places.isNotEmpty()) {
                                    Text(
                                        "Reported at: ${alert.places.joinToString(", ")}",
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                }
                            }
                        }
                    }
                    item { Spacer(Modifier.height(24.dp)) }
                }
            }
        }
    }
}
