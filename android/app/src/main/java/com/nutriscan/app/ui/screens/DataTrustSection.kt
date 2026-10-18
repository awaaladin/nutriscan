package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.HelpOutline
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.text.KeyboardOptions
import com.nutriscan.app.data.model.DataTrust
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsOutlinedButton
import com.nutriscan.app.ui.theme.NsAmber
import com.nutriscan.app.ui.theme.NsCharcoal400
import com.nutriscan.app.ui.theme.NsEmerald500
import com.nutriscan.app.ui.theme.NsEmerald700
import kotlinx.coroutines.launch

fun trustColor(level: String): Color = when (level) {
    "verified" -> NsEmerald700
    "corroborated" -> NsEmerald500
    "sourced" -> Color(0xFF2E7DAF)
    else -> NsCharcoal400
}

private fun trustIcon(level: String): ImageVector = when (level) {
    "verified" -> Icons.Rounded.Verified
    "corroborated", "sourced" -> Icons.Rounded.CheckCircle
    else -> Icons.Rounded.HelpOutline
}

/** A small badge for lists (search results): the trust level and nothing more. */
@Composable
fun TrustBadge(level: String, headline: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(trustIcon(level), contentDescription = null, tint = trustColor(level), modifier = Modifier.size(16.dp))
        Spacer(Modifier.width(4.dp))
        Text(headline, style = MaterialTheme.typography.labelMedium, color = trustColor(level))
    }
}

/**
 * How far this product's data can be trusted and exactly why: the level, the evidence
 * behind it, any disagreement between sources, and links to the sources. Trust is
 * computed on the server from evidence, never asserted -- two independent sources must
 * agree before it reads "corroborated". Anyone can report a correction.
 */
@Composable
fun DataTrustCard(
    trust: DataTrust,
    checking: Boolean,
    filledIn: List<String>,
    onReportCorrection: () -> Unit,
) {
    val color = trustColor(trust.level)
    val uriHandler = LocalUriHandler.current
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.10f)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text("Data trust", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(trustIcon(trust.level), contentDescription = null, tint = color, modifier = Modifier.size(22.dp))
                Spacer(Modifier.width(8.dp))
                Text(trust.headline, style = MaterialTheme.typography.titleMedium, color = color)
            }
            Spacer(Modifier.height(6.dp))
            trust.evidence.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 2.dp)) }
            trust.warnings.forEach {
                Text("⚠ $it", style = MaterialTheme.typography.bodySmall, color = NsAmber, modifier = Modifier.padding(vertical = 2.dp))
            }
            if (filledIn.isNotEmpty()) {
                Text(
                    "Just added from other sources: ${filledIn.joinToString(", ") { it.replace('_', ' ') }}.",
                    style = MaterialTheme.typography.bodySmall,
                    color = color,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
            if (checking) {
                Text("Checking other sources…", style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(top = 6.dp))
            }
            trust.sources.forEach { source ->
                TextButton(onClick = { uriHandler.openUri(source.url) }) {
                    Text(source.label.ifBlank { source.url }, style = MaterialTheme.typography.labelSmall, maxLines = 1)
                }
            }
            Spacer(Modifier.height(4.dp))
            NsOutlinedButton(text = "Something wrong? Report a correction", onClick = onReportCorrection, modifier = Modifier.fillMaxWidth())
        }
    }
}

private val correctable = listOf(
    "sugar_g" to "Sugar (g/100)",
    "saturated_fat_g" to "Saturated fat (g/100)",
    "sodium_mg" to "Sodium (mg/100)",
    "calories_kcal" to "Calories (kcal/100)",
    "carbohydrates_g" to "Carbohydrates (g/100)",
    "fiber_g" to "Fibre (g/100)",
    "protein_g" to "Protein (g/100)",
    "ingredients_text" to "Ingredients",
    "nafdac_number" to "NAFDAC number",
)

/** Report that one value is wrong. It's a vote: it is applied only once enough credible
 * people agree (or our team reviews it), so no single account can rewrite the data. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CorrectionDialog(repository: NutriScanRepository, barcode: String, onDismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var field by remember { mutableStateOf("sugar_g") }
    var value by remember { mutableStateOf("") }
    var reason by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var failed by remember { mutableStateOf(false) }
    val isText = field == "ingredients_text" || field == "nafdac_number"

    AlertDialog(
        onDismissRequest = { if (!sending) onDismiss() },
        title = { Text("Report a correction") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                Text(
                    "Which value is wrong? Copy the right one from the pack. We apply it once enough people agree.",
                    style = MaterialTheme.typography.bodySmall,
                )
                Spacer(Modifier.height(8.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    correctable.forEach { (key, label) ->
                        FilterChip(selected = field == key, onClick = { field = key; message = null }, label = { Text(label) })
                    }
                }
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = value,
                    onValueChange = { value = it.take(3000) },
                    label = { Text("The correct value") },
                    keyboardOptions = KeyboardOptions(keyboardType = if (isText) KeyboardType.Text else KeyboardType.Decimal),
                    minLines = if (field == "ingredients_text") 3 else 1,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it.take(300) },
                    label = { Text("How do you know? (optional)") },
                    modifier = Modifier.fillMaxWidth(),
                )
                message?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(it, style = MaterialTheme.typography.bodySmall, color = if (failed) MaterialTheme.colorScheme.error else NsEmerald700)
                }
            }
        },
        confirmButton = {
            TextButton(
                enabled = value.isNotBlank() && !sending && message == null || failed,
                onClick = {
                    sending = true
                    scope.launch {
                        repository.submitCorrection(barcode, field, value.trim(), reason.trim())
                            .onSuccess { failed = false; message = it.detail }
                            .onFailure { failed = true; message = it.message ?: "Couldn't send that. Please try again." }
                        sending = false
                    }
                },
            ) { Text(if (sending) "Sending…" else "Send") }
        },
        dismissButton = { TextButton(enabled = !sending, onClick = onDismiss) { Text(if (message != null && !failed) "Done" else "Cancel") } },
    )
}
