package com.nutriscan.app.ui.screens

import android.content.Intent
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.HealthLog
import com.nutriscan.app.data.model.HealthSummary
import com.nutriscan.app.data.model.PreferencesUpdateRequest
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.data.repository.PlanRequiredException
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsAmber
import kotlinx.coroutines.launch

private data class Tracker(val kind: String, val title: String, val plan: String, val unlockText: String)

private val TRACKERS = listOf(
    Tracker("weight", "Weight", "Pro", "Track your weight, BMI and progress to your goal."),
    Tracker("blood_pressure", "Blood pressure", "Pro Plus", "Log readings and see how often you're under 130/80."),
    Tracker("glucose", "Blood sugar", "Pro Care", "Log fasting and after-meal readings against your targets."),
)

private val TIMINGS = listOf(
    "fasting" to "Fasting",
    "before_meal" to "Before a meal",
    "after_meal" to "2h after a meal",
    "random" to "Random",
)

private data class Tool(val id: String, val title: String, val plan: String, val description: String)

private val TOOLS = listOf(
    Tool("meal_plan", "7-day meal plan", "Pro Plus", "Affordable Nigerian meals built around your goal and readings."),
    Tool("progress_report", "Weekly progress report", "Pro Plus", "What your readings and scans show, and what to change."),
    Tool("doctor_summary", "Doctor-visit summary", "Pro Care", "A one-page summary of your readings to show your doctor."),
)

/** The Pro health tools: trackers for weight, blood pressure and blood sugar, and AI-written
 * meal plans, progress reports and doctor summaries built from them. */
@Composable
fun HealthScreen(repository: NutriScanRepository, onBack: () -> Unit, onOpenPlans: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var summary by remember { mutableStateOf<HealthSummary?>(null) }
    var selected by rememberSaveable { mutableStateOf(0) }
    val logs = remember { mutableStateListOf<HealthLog>() }
    var message by remember { mutableStateOf<String?>(null) }
    var toolResult by remember { mutableStateOf<Pair<String, String>?>(null) }
    var runningTool by remember { mutableStateOf<String?>(null) }

    val tracker = TRACKERS[selected]
    val unlocked = summary?.unlocked?.get(tracker.kind) == true

    suspend fun refresh() {
        repository.healthSummary().onSuccess { summary = it }
        repository.healthLogs(tracker.kind).onSuccess { logs.clear(); logs.addAll(it) }
    }

    LaunchedEffect(selected) {
        message = null
        refresh()
    }

    NsScreenScaffold(title = "My health", onBack = onBack) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            TabRow(selectedTabIndex = selected) {
                TRACKERS.forEachIndexed { index, t ->
                    Tab(selected = selected == index, onClick = { selected = index }, text = { Text(t.title) })
                }
            }
            Column(modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
                summary?.alerts?.forEach { alert ->
                    Card(
                        colors = CardDefaults.cardColors(containerColor = NsAmber.copy(alpha = 0.25f)),
                        modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp),
                    ) {
                        Row(modifier = Modifier.padding(12.dp)) {
                            Icon(Icons.Rounded.Warning, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text(alert, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
                if (summary == null) {
                    Text("Loading…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else if (!unlocked) {
                    LockedCard(
                        title = "${tracker.title} tracker",
                        text = "${tracker.unlockText} Part of NutriScan ${tracker.plan}.",
                        onOpenPlans = onOpenPlans,
                    )
                } else {
                    SummaryCard(tracker.kind, summary!!)
                    Spacer(Modifier.height(12.dp))
                    if (tracker.kind == "weight") {
                        WeightGoalCard(summary!!) { height, target ->
                            scope.launch {
                                repository.updatePreferences(PreferencesUpdateRequest(height_cm = height, target_weight_kg = target))
                                    .onSuccess { refresh() }
                                    .onFailure { message = it.message }
                            }
                        }
                        Spacer(Modifier.height(12.dp))
                    }
                    AddReadingCard(tracker.kind) { log ->
                        scope.launch {
                            repository.addHealthLog(log)
                                .onSuccess { saved ->
                                    message = saved.alert ?: "Saved."
                                    refresh()
                                }
                                .onFailure { message = it.message }
                        }
                    }
                    message?.let {
                        Spacer(Modifier.height(8.dp))
                        Text(it, style = MaterialTheme.typography.bodyMedium)
                    }
                    Spacer(Modifier.height(12.dp))
                    Text("Recent readings", style = MaterialTheme.typography.titleSmall)
                    if (logs.isEmpty()) {
                        Text("Nothing logged yet.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    logs.take(30).forEach { log ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(modifier = Modifier.weight(1f).padding(vertical = 4.dp)) {
                                Text(describe(log), style = MaterialTheme.typography.bodyMedium)
                                Text(
                                    (log.measured_at ?: "").take(16).replace("T", " "),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            IconButton(onClick = {
                                val id = log.id ?: return@IconButton
                                scope.launch { repository.deleteHealthLog(id).onSuccess { refresh() } }
                            }) { Icon(Icons.Rounded.Delete, contentDescription = "Delete reading") }
                        }
                    }
                }

                Spacer(Modifier.height(20.dp))
                Text("AI health tools", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Written from your readings, profile and scans. Each uses 3 credits.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                TOOLS.forEach { tool ->
                    val toolUnlocked = summary?.unlocked?.get(tool.id) == true
                    Card(modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp), shape = RoundedCornerShape(16.dp)) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text(tool.title, style = MaterialTheme.typography.titleSmall)
                            Text(tool.description, style = MaterialTheme.typography.bodySmall)
                            Spacer(Modifier.height(8.dp))
                            if (toolUnlocked) {
                                OutlinedButton(
                                    enabled = runningTool == null,
                                    onClick = {
                                        runningTool = tool.id
                                        scope.launch {
                                            repository.runHealthTool(tool.id)
                                                .onSuccess { toolResult = tool.title to it.text }
                                                .onFailure {
                                                    message = it.message
                                                    if (it is PlanRequiredException) onOpenPlans()
                                                }
                                            runningTool = null
                                        }
                                    },
                                ) { Text(if (runningTool == tool.id) "Writing…" else "Create") }
                            } else {
                                TextButton(onClick = onOpenPlans) {
                                    Icon(Icons.Rounded.Lock, contentDescription = null, modifier = Modifier.height(16.dp))
                                    Spacer(Modifier.width(4.dp))
                                    Text("Part of NutriScan ${tool.plan}")
                                }
                            }
                        }
                    }
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    "Targets shown are general guideline targets for most adults (American Diabetes Association, " +
                        "American Heart Association, WHO). Your doctor's targets come first. NutriScan gives general " +
                        "information, not medical advice. In an emergency call 112.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }

    toolResult?.let { (title, text) ->
        AlertDialog(
            onDismissRequest = { toolResult = null },
            title = { Text(title) },
            text = { Column(modifier = Modifier.verticalScroll(rememberScrollState())) { Text(text) } },
            confirmButton = { TextButton(onClick = { toolResult = null }) { Text("Done") } },
            dismissButton = {
                TextButton(onClick = {
                    val share = Intent(Intent.ACTION_SEND).apply {
                        type = "text/plain"
                        putExtra(Intent.EXTRA_SUBJECT, "NutriScan: $title")
                        putExtra(Intent.EXTRA_TEXT, "$text\n\nMade with NutriScan. General information, not medical advice.")
                    }
                    context.startActivity(Intent.createChooser(share, "Share"))
                }) { Text("Share") }
            },
        )
    }
}

private fun describe(log: HealthLog): String = when (log.kind) {
    "weight" -> "${log.value} kg"
    "blood_pressure" -> "${log.systolic}/${log.diastolic} mmHg"
    else -> "${log.value?.toInt()} mg/dL · ${TIMINGS.firstOrNull { it.first == log.timing }?.second ?: "Random"}"
} + if (log.note.isNotBlank()) " · ${log.note}" else ""

@Composable
private fun LockedCard(title: String, text: String, onOpenPlans: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp)) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Rounded.Lock, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(title, style = MaterialTheme.typography.titleMedium)
            }
            Spacer(Modifier.height(8.dp))
            Text(text, style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(12.dp))
            NsButton(text = "See plans", onClick = onOpenPlans, modifier = Modifier.fillMaxWidth())
        }
    }
}

@Composable
private fun SummaryCard(kind: String, s: HealthSummary) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
    ) {
        Column(modifier = Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            when (kind) {
                "weight" -> s.weight?.let { w ->
                    Big("${w.latest_kg} kg")
                    Text("${signed(w.change_kg)} kg in the last 30 days")
                    w.bmi?.let { Text("BMI $it (healthy range 18.5–24.9)") }
                    w.to_target_kg?.let { Text(if (it > 0) "$it kg to your goal of ${w.target_kg} kg" else "You've reached your goal of ${w.target_kg} kg") }
                } ?: Text("Log your weight to see your trend.")
                "blood_pressure" -> s.blood_pressure?.let { b ->
                    Big(b.latest)
                    Text("7-day average ${b.avg_7d}")
                    Text("${b.in_target_pct}% of readings ${b.target}")
                } ?: Text("Log a reading to see your trend. Target for most adults: under 130/80.")
                else -> s.glucose?.let { g ->
                    Big("${g.latest_mg_dl.toInt()} mg/dL")
                    g.avg_fasting_mg_dl?.let { Text("Average fasting: ${it.toInt()} mg/dL") }
                    g.avg_after_meal_mg_dl?.let { Text("Average after meals: ${it.toInt()} mg/dL") }
                    Text("${g.in_target_pct}% in target (${g.target})")
                    if (g.lows > 0) Text("${g.lows} low reading(s) under 70 mg/dL. Tell your doctor.", fontWeight = FontWeight.Bold)
                } ?: Text("Log a reading to see your trend. Targets for most adults: 80–130 mg/dL fasting, under 180 after meals.")
            }
        }
    }
}

@Composable
private fun Big(text: String) = Text(text, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)

private fun signed(value: Double) = if (value > 0) "+$value" else "$value"

@Composable
private fun WeightGoalCard(s: HealthSummary, onSave: (Int?, Double?) -> Unit) {
    var height by remember(s.height_cm) { mutableStateOf(s.height_cm?.toString() ?: "") }
    var target by remember(s.target_weight_kg) { mutableStateOf(s.target_weight_kg?.toString() ?: "") }
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text("Your goal", style = MaterialTheme.typography.titleSmall)
            Row {
                OutlinedTextField(
                    value = height, onValueChange = { height = it.filter(Char::isDigit).take(3) },
                    label = { Text("Height (cm)") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                OutlinedTextField(
                    value = target, onValueChange = { target = it.filter { c -> c.isDigit() || c == '.' }.take(5) },
                    label = { Text("Goal (kg)") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.weight(1f),
                )
            }
            TextButton(onClick = { onSave(height.toIntOrNull(), target.toDoubleOrNull()) }) { Text("Save goal") }
        }
    }
}

@Composable
private fun AddReadingCard(kind: String, onAdd: (HealthLog) -> Unit) {
    var value by remember(kind) { mutableStateOf("") }
    var systolic by remember(kind) { mutableStateOf("") }
    var diastolic by remember(kind) { mutableStateOf("") }
    var timing by remember(kind) { mutableStateOf("fasting") }
    var note by remember(kind) { mutableStateOf("") }
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text("Add a reading", style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(6.dp))
            if (kind == "blood_pressure") {
                Row {
                    OutlinedTextField(
                        value = systolic, onValueChange = { systolic = it.filter(Char::isDigit).take(3) },
                        label = { Text("Top (systolic)") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(8.dp))
                    OutlinedTextField(
                        value = diastolic, onValueChange = { diastolic = it.filter(Char::isDigit).take(3) },
                        label = { Text("Bottom (diastolic)") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.weight(1f),
                    )
                }
            } else {
                OutlinedTextField(
                    value = value, onValueChange = { value = it.filter { c -> c.isDigit() || c == '.' }.take(6) },
                    label = { Text(if (kind == "weight") "Weight (kg)" else "Blood sugar (mg/dL)") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), modifier = Modifier.fillMaxWidth(),
                )
            }
            if (kind == "glucose") {
                Spacer(Modifier.height(6.dp))
                Row(modifier = Modifier.horizontalScroll(rememberScrollState())) {
                    TIMINGS.forEach { (id, label) ->
                        FilterChip(selected = timing == id, onClick = { timing = id }, label = { Text(label) })
                        Spacer(Modifier.width(6.dp))
                    }
                }
            }
            OutlinedTextField(
                value = note, onValueChange = { note = it.take(200) },
                label = { Text("Note (optional)") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            NsButton(
                text = "Save reading",
                onClick = {
                    onAdd(
                        HealthLog(
                            kind = kind,
                            value = value.toDoubleOrNull(),
                            systolic = systolic.toIntOrNull(),
                            diastolic = diastolic.toIntOrNull(),
                            timing = if (kind == "glucose") timing else "",
                            note = note.trim(),
                        ),
                    )
                    value = ""; systolic = ""; diastolic = ""; note = ""
                },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}
