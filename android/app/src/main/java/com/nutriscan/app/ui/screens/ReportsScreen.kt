package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.nutriscan.app.data.model.ProductReport
import com.nutriscan.app.data.model.ReportsResponse
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.IntegrityCard
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsEmerald700
import com.nutriscan.app.ui.theme.NsRed
import kotlinx.coroutines.launch

@Composable
fun ReportsScreen(
    repository: NutriScanRepository,
    barcode: String,
    onBack: () -> Unit,
    onAddReport: () -> Unit,
    onDispute: () -> Unit,
) {
    var data by remember { mutableStateOf<ReportsResponse?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var notice by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    // Re-runs when returning from the report form, so the new report and the
    // updated percentage show up without a manual refresh.
    LaunchedEffect(barcode) {
        repository.reports(barcode)
            .onSuccess { data = it; error = null }
            .onFailure { error = it.message }
    }

    NsScreenScaffold(title = "Community reports", onBack = onBack) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 24.dp)) {
            val current = data
            when {
                error != null -> Text(error ?: "", color = MaterialTheme.colorScheme.error)
                current == null -> CircularProgressIndicator()
                else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    item {
                        Spacer(Modifier.height(8.dp))
                        IntegrityCard(current.integrity)
                        Spacer(Modifier.height(12.dp))
                        NsButton(text = "Report real or fake", onClick = onAddReport, modifier = Modifier.fillMaxWidth())
                        TextButton(onClick = onDispute) { Text("I'm the manufacturer -- dispute this") }
                        notice?.let {
                            Spacer(Modifier.height(8.dp))
                            Text(it, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    if (current.reports.isEmpty()) {
                        item {
                            Text(
                                "Nobody has reported this product yet. Bought it? Tell others if it was real.",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    items(current.reports, key = { it.id }) { report ->
                        ReportCard(report, onFlag = {
                            scope.launch {
                                repository.flagReport(report.id)
                                    .onSuccess { notice = "Thanks -- we'll review that report." }
                                    .onFailure { notice = it.message }
                            }
                        })
                    }
                    item { Spacer(Modifier.height(24.dp)) }
                }
            }
        }
    }
}

@Composable
private fun ReportCard(report: ProductReport, onFlag: () -> Unit) {
    val isReal = report.verdict == "real"
    Card(shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row {
                Text(
                    if (isReal) "Real" else "Fake",
                    style = MaterialTheme.typography.titleSmall,
                    color = if (isReal) NsEmerald700 else NsRed,
                    modifier = Modifier.weight(1f),
                )
                Text(report.username, style = MaterialTheme.typography.labelMedium)
            }
            if (report.where_bought.isNotBlank()) {
                Text("Bought at: ${report.where_bought}", style = MaterialTheme.typography.bodySmall)
            }
            if (report.batch_number.isNotBlank()) {
                Text("Batch: ${report.batch_number}", style = MaterialTheme.typography.bodySmall)
            }
            if (report.nafdac_number.isNotBlank()) {
                Text("NAFDAC no.: ${report.nafdac_number}", style = MaterialTheme.typography.bodySmall)
            }
            if (report.comment.isNotBlank()) {
                Spacer(Modifier.height(6.dp))
                Text(report.comment, style = MaterialTheme.typography.bodyMedium)
            }
            if (report.photos.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(report.photos, key = { it.id }) { photo ->
                        AsyncImage(
                            model = photo.image,
                            contentDescription = "Report photo",
                            contentScale = ContentScale.Crop,
                            modifier = Modifier.size(96.dp).clip(RoundedCornerShape(12.dp)),
                        )
                    }
                }
            }
            TextButton(onClick = onFlag) { Text("Flag as abusive or false") }
        }
    }
}
