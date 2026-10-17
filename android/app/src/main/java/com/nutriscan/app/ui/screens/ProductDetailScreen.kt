package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.VolumeUp
import androidx.compose.material.icons.rounded.Forum
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.local.AppPreferencesManager
import com.nutriscan.app.data.model.ProductReport
import com.nutriscan.app.data.model.ScanResponse
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.MainViewModel
import com.nutriscan.app.ui.ScanUiState
import com.nutriscan.app.ui.components.HealthLabelChip
import com.nutriscan.app.ui.components.IntegrityCard
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsOutlinedButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsAmber
import com.nutriscan.app.ui.theme.NsCharcoal400
import com.nutriscan.app.ui.theme.NsEmerald700
import com.nutriscan.app.ui.theme.NsRed
import com.nutriscan.app.ui.util.rememberSpeaker
import com.nutriscan.app.ui.util.spokenSummary

/**
 * Everything about a scanned product in one place: the health verdict, how far
 * to trust it (authenticity), what the community says, the nutrition table
 * coloured against WHO thresholds, and the ingredients ("materials") it is made
 * from. Also reachable from History, so a past scan opens exactly the same way.
 * The result can be read aloud, and any question can be put to the assistant.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ProductDetailScreen(
    viewModel: MainViewModel,
    repository: NutriScanRepository,
    preferences: AppPreferencesManager,
    onBack: () -> Unit,
    onViewAnalysis: () -> Unit,
    onOpenReports: (barcode: String) -> Unit,
    onAsk: (barcode: String) -> Unit,
    onPhotographTable: (barcode: String) -> Unit,
    onTypeValues: (barcode: String) -> Unit,
) {
    val scanState by viewModel.scanState.collectAsState()
    val result = (scanState as? ScanUiState.Success)?.result
    val speaker = rememberSpeaker()
    val autoRead by preferences.autoReadAloud.collectAsState(initial = false)

    // Speak the verdict automatically if the user turned that on.
    LaunchedEffect(result?.product?.barcode, autoRead) {
        if (autoRead && result != null) speaker.speak(spokenSummary(result))
    }

    // A product with no score can't be judged, so ask for the missing piece immediately
    // rather than leaving the user to find the card. Once per visit.
    var promptDismissed by rememberSaveable(result?.product?.barcode) { mutableStateOf(false) }
    if (result != null && result.label == "Incomplete" && !promptDismissed) {
        AlertDialog(
            onDismissRequest = { promptDismissed = true },
            title = { Text("We need the nutrition table") },
            text = {
                Column {
                    Text(
                        "We couldn't find this product's nutrition values, so we can't give it a health score yet. " +
                            "Take a photo of the nutrition table on the pack and we'll read it and score the product -- " +
                            "and next time it's instant.",
                    )
                    TextButton(onClick = { promptDismissed = true; onTypeValues(result.product.barcode) }) {
                        Text("Type the values instead")
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { promptDismissed = true; onPhotographTable(result.product.barcode) }) {
                    Text("Photograph the table")
                }
            },
            dismissButton = { TextButton(onClick = { promptDismissed = true }) { Text("Later") } },
        )
    }

    NsScreenScaffold(title = "Product", onBack = { speaker.stop(); onBack() }) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp, vertical = 16.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            if (result == null) {
                Text("No product loaded.")
                return@Column
            }
            val product = result.product

            // --- Who/what it is, and the verdict ---------------------------------
            Text(product.name, style = MaterialTheme.typography.headlineSmall)
            product.brand?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(4.dp))
            Text(
                "Barcode ${product.barcode}" +
                    (product.nafdac_number?.takeIf { it.isNotBlank() }?.let {
                        " · NAFDAC $it" + if (product.nafdac_verified) " ✓ confirmed" else " (not yet confirmed)"
                    } ?: ""),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (result.label != null) {
                Spacer(Modifier.height(10.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    HealthLabelChip(result.label)
                    Spacer(Modifier.width(10.dp))
                    if (result.score != null) {
                        Text("${result.score}/10", style = MaterialTheme.typography.titleMedium)
                    } else {
                        Text("No score yet", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    result.diabetic_risk?.let {
                        Spacer(Modifier.width(10.dp))
                        Text("Diabetic risk: $it", style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }

            // --- Missing data: say so, and offer the way to fix it ------------------------------
            if (result.insufficient_data) {
                Spacer(Modifier.height(12.dp))
                IncompleteDataCard(
                    result = result,
                    onPhotographTable = { onPhotographTable(product.barcode) },
                    onTypeValues = { onTypeValues(product.barcode) },
                )
            }

            // --- Read aloud / ask -------------------------------------------------
            Spacer(Modifier.height(14.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                NsOutlinedButton(
                    text = when {
                        speaker.available == false -> "Voice unavailable"
                        speaker.isSpeaking -> "Stop"
                        else -> "Read aloud"
                    },
                    enabled = speaker.available != false,
                    onClick = { if (speaker.isSpeaking) speaker.stop() else speaker.speak(spokenSummary(result)) },
                    modifier = Modifier.weight(1f),
                )
                NsButton(text = "Ask about it", onClick = { onAsk(product.barcode) }, modifier = Modifier.weight(1f))
            }

            // --- Where this result came from -----------------------------------------
            val sourceNote = when (result.source) {
                "ai" -> "Researched from your photos by AI and saved. Scanning this barcode again is instant."
                "twin" -> "Matched by NAFDAC number to a product already in our database."
                "database" -> "From the NutriScan database."
                else -> null
            }
            sourceNote?.let {
                Spacer(Modifier.height(10.dp))
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
            }
            if (result.is_estimated) {
                Spacer(Modifier.height(4.dp))
                Text(
                    "Details were read from photos and may be inaccurate -- check them against the pack.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            // --- Authenticity and community ---------------------------------------------
            Spacer(Modifier.height(16.dp))
            product.integrity?.let { IntegrityCard(it) }
            Spacer(Modifier.height(12.dp))
            CommunityCard(
                repository = repository,
                barcode = product.barcode,
                onOpenReports = { onOpenReports(product.barcode) },
            )

            // --- Nutrition -----------------------------------------------------------------
            Spacer(Modifier.height(20.dp))
            Text("Nutrition (per 100g)", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            Card(shape = RoundedCornerShape(16.dp)) {
                Column(modifier = Modifier.padding(horizontal = 16.dp)) {
                    NutritionRow("Calories", product.calories_kcal, "kcal", null)
                    HorizontalDivider()
                    NutritionRow("Sugar", product.sugar_g, "g", whoTier(result, "sugar"))
                    HorizontalDivider()
                    NutritionRow("Saturated fat", product.saturated_fat_g, "g", whoTier(result, "saturated_fat"))
                    HorizontalDivider()
                    NutritionRow("Sodium", product.sodium_mg, "mg", whoTier(result, "sodium"))
                    HorizontalDivider()
                    NutritionRow("Carbohydrates", product.carbohydrates_g, "g", null)
                    HorizontalDivider()
                    NutritionRow("Fiber", product.fiber_g, "g", null)
                    HorizontalDivider()
                    NutritionRow("Protein", product.protein_g, "g", null)
                }
            }
            if (result.insufficient_data) {
                Spacer(Modifier.height(4.dp))
                Text(
                    "Some values are missing, so the score is based on what is available.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            // --- What it's made of ---------------------------------------------------------
            Spacer(Modifier.height(20.dp))
            Text("What it's made of", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            val ingredients = splitIngredients(product.ingredients_text)
            if (ingredients.isEmpty()) {
                Text("Ingredients not available for this product.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ingredients.forEach { ingredient ->
                        AssistChip(onClick = {}, label = { Text(ingredient) }, modifier = Modifier.padding(bottom = 4.dp))
                    }
                }
                Text(
                    "Listed in order of quantity, most first.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (product.additives.isNotEmpty()) {
                Spacer(Modifier.height(14.dp))
                Text("Additives", style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(6.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    product.additives.forEach { additive ->
                        AssistChip(onClick = {}, label = { Text(readableAdditive(additive)) }, modifier = Modifier.padding(bottom = 4.dp))
                    }
                }
            }

            Spacer(Modifier.height(24.dp))
            NsButton(text = "View health analysis", onClick = onViewAnalysis, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(24.dp))
        }
    }
}

/** Shown whenever nutrition values are missing. With no numbers at all there is no
 * score (a green 10/10 would be a guess); with some missing, the verdict is only a
 * floor. Either way the fix is one tap: photograph the table or type the values. */
@Composable
private fun IncompleteDataCard(result: ScanResponse, onPhotographTable: () -> Unit, onTypeValues: () -> Unit) {
    val missing = result.missing_nutrients.joinToString(", ").ifBlank { "nutrition" }
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = androidx.compose.material3.CardDefaults.cardColors(containerColor = NsAmber.copy(alpha = 0.15f)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                if (result.score == null) "Not enough data to score this product" else "Score based on incomplete data",
                style = MaterialTheme.typography.titleSmall,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                if (result.score == null) {
                    "We don't have this product's $missing information, so we won't guess a score. " +
                        "Add the nutrition table to get a real one."
                } else {
                    "Missing: $missing. Those values could only make this verdict worse, never better."
                },
                style = MaterialTheme.typography.bodySmall,
            )
            if ("likely_high_sugar" in result.flags) {
                Spacer(Modifier.height(4.dp))
                Text(
                    "Sugar is one of the first ingredients, so it is probably high in sugar.",
                    style = MaterialTheme.typography.bodySmall,
                    color = NsRed,
                )
            }
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                NsButton(text = "Photograph the table", onClick = onPhotographTable, modifier = Modifier.weight(1f))
                NsOutlinedButton(text = "Type the values", onClick = onTypeValues, modifier = Modifier.weight(1f))
            }
        }
    }
}

/** What the community says: the real/fake split, and the latest few reports
 * with where the product was bought. The full list and the form to add a report
 * are one tap away. */
@Composable
private fun CommunityCard(repository: NutriScanRepository, barcode: String, onOpenReports: () -> Unit) {
    var reports by remember(barcode) { mutableStateOf<List<ProductReport>?>(null) }
    var counts by remember(barcode) { mutableStateOf<Pair<Int, Int>?>(null) }
    var failed by remember(barcode) { mutableStateOf(false) }

    LaunchedEffect(barcode) {
        repository.reports(barcode)
            .onSuccess {
                reports = it.reports
                counts = it.integrity.real_votes to it.integrity.fake_votes
            }
            .onFailure { failed = true }
    }

    Card(shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Rounded.Forum, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Community", style = MaterialTheme.typography.titleMedium)
            }
            Spacer(Modifier.height(8.dp))
            when {
                failed -> Text(
                    "Couldn't load community reports right now.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                reports == null -> Text("Loading…", style = MaterialTheme.typography.bodySmall)
                reports!!.isEmpty() -> Text(
                    "Nobody has reported on this product yet. Bought it? Tell others if it was real.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                else -> {
                    counts?.let { (real, fake) ->
                        Row {
                            Text("$real say real", color = NsEmerald700, style = MaterialTheme.typography.labelLarge)
                            Text("  ·  ", style = MaterialTheme.typography.labelLarge)
                            Text("$fake say fake", color = if (fake > 0) NsRed else NsCharcoal400, style = MaterialTheme.typography.labelLarge)
                        }
                        Spacer(Modifier.height(6.dp))
                    }
                    reports!!.take(3).forEach { report ->
                        val isReal = report.verdict == "real"
                        Text(
                            (if (isReal) "Real" else "Fake") +
                                (report.where_bought.takeIf { it.isNotBlank() }?.let { " · bought at $it" } ?: ""),
                            style = MaterialTheme.typography.labelMedium,
                            color = if (isReal) NsEmerald700 else NsRed,
                        )
                        if (report.comment.isNotBlank()) {
                            Text("“${report.comment}”", style = MaterialTheme.typography.bodySmall)
                        }
                        Spacer(Modifier.height(6.dp))
                    }
                }
            }
            Spacer(Modifier.height(4.dp))
            NsOutlinedButton(text = "See all reports & add yours", onClick = onOpenReports, modifier = Modifier.fillMaxWidth())
        }
    }
}

private enum class WhoTier(val label: String) { LOW("Low"), MODERATE("Moderate"), HIGH("High") }

/** The WHO tier for one nutrient, taken from the flags the server's scoring
 * engine already produced (e.g. "high_sugar") -- never recomputed here, so the
 * colours can't disagree with the score. A nutrient with no flag was "low". */
private fun whoTier(result: ScanResponse, nutrient: String): WhoTier? = when {
    "high_$nutrient" in result.flags -> WhoTier.HIGH
    "moderate_$nutrient" in result.flags -> WhoTier.MODERATE
    else -> WhoTier.LOW
}

@Composable
private fun NutritionRow(label: String, value: Double?, unit: String, tier: WhoTier?) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, modifier = Modifier.weight(1f))
        if (value != null && tier != null) {
            val color: Color = when (tier) {
                WhoTier.LOW -> NsEmerald700
                WhoTier.MODERATE -> NsAmber
                WhoTier.HIGH -> NsRed
            }
            Text(tier.label, color = color, style = MaterialTheme.typography.labelMedium)
            Spacer(Modifier.width(10.dp))
        }
        Text(if (value != null) "${trimNumber(value)} $unit" else "N/A", style = MaterialTheme.typography.titleSmall)
    }
}

private fun trimNumber(value: Double): String =
    if (value == value.toLong().toDouble()) value.toLong().toString() else "%.1f".format(value)

/** Splits an ingredient list on commas and semicolons, but not inside brackets,
 * so "Flour (wheat, iron)" stays one item. */
private fun splitIngredients(text: String?): List<String> {
    if (text.isNullOrBlank()) return emptyList()
    val items = mutableListOf<String>()
    val current = StringBuilder()
    var depth = 0
    for (char in text) {
        when {
            char == '(' || char == '[' -> { depth++; current.append(char) }
            char == ')' || char == ']' -> { depth = (depth - 1).coerceAtLeast(0); current.append(char) }
            (char == ',' || char == ';') && depth == 0 -> { items += current.toString(); current.clear() }
            else -> current.append(char)
        }
    }
    items += current.toString()
    return items.map { it.trim().trimEnd('.').replaceFirstChar { c -> c.uppercase() } }.filter { it.isNotBlank() }
}

/** Open Food Facts tags look like "en:e330" or "en:citric-acid". */
private fun readableAdditive(tag: String): String {
    val name = tag.substringAfter(':').replace('-', ' ')
    return if (Regex("^e\\d+[a-z]?$", RegexOption.IGNORE_CASE).matches(name)) name.uppercase() else name.replaceFirstChar { it.uppercase() }
}
