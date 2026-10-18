package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.AssistantSettings
import com.nutriscan.app.data.repository.NutriScanRepository
import kotlinx.coroutines.launch

/**
 * What the assistant knows about you, and the privacy choices around it. Shown once on
 * first use (with the privacy explanation up front) and from the settings button after.
 *
 * Health information is sensitive, so: chats are private to the account, photos are not
 * stored, sharing chats to improve NutriScan is OFF unless switched on here, and every
 * conversation can be deleted.
 */
@Composable
fun AssistantSettingsDialog(
    repository: NutriScanRepository,
    firstTime: Boolean,
    onDismiss: () -> Unit,
    onChatsDeleted: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var loaded by remember { mutableStateOf(false) }
    var notes by remember { mutableStateOf("") }
    var allowTraining by remember { mutableStateOf(false) }
    var saving by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        repository.assistantSettings()
            .onSuccess { notes = it.health_notes; allowTraining = it.allow_training_use }
            .onFailure { error = "Couldn't load your settings (${it.message}). You can still chat." }
        loaded = true
    }

    AlertDialog(
        onDismissRequest = { if (!saving) onDismiss() },
        title = { Text(if (firstTime) "Your private health assistant" else "Assistant settings") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                Text(
                    "Your chats are private to your account. Photos you attach are read for that one answer and are not saved. " +
                        "This is general information, not medical advice.",
                    style = MaterialTheme.typography.bodySmall,
                )
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = notes,
                    onValueChange = { notes = it.take(500) },
                    label = { Text("About you (optional)") },
                    supportingText = { Text("Allergies, conditions, medicines. Write allergies like \"Allergic to peanuts\": NutriScan then warns you about them on every scan. Also personalises chat answers. ${notes.length}/500") },
                    minLines = 3,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                    Column(modifier = Modifier.weight(1f).padding(end = 8.dp)) {
                        Text("Help improve NutriScan", style = MaterialTheme.typography.titleSmall)
                        Text(
                            "Let NutriScan learn from my chats. They're anonymised first (no name, email or phone), only used " +
                                "if I rate the answers, and I can switch this off any time. Off by default.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Switch(checked = allowTraining, onCheckedChange = { allowTraining = it })
                }
                error?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
                if (!firstTime) {
                    Spacer(Modifier.height(8.dp))
                    TextButton(onClick = { confirmDelete = true }) {
                        Text("Delete all my chats", color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                enabled = loaded && !saving,
                onClick = {
                    saving = true
                    scope.launch {
                        repository.saveAssistantSettings(AssistantSettings(notes.trim(), allowTraining))
                            .onSuccess { onDismiss() }
                            .onFailure { error = it.message ?: "Couldn't save. Please try again." }
                        saving = false
                    }
                },
            ) { Text(if (saving) "Saving…" else if (firstTime) "Continue" else "Save") }
        },
        dismissButton = { TextButton(enabled = !saving, onClick = onDismiss) { Text(if (firstTime) "Skip" else "Cancel") } },
    )

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete all chats?") },
            text = { Text("Every conversation with the assistant is permanently deleted from your account. This can't be undone.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmDelete = false
                    scope.launch {
                        repository.deleteAllChats()
                            .onSuccess { onChatsDeleted(); onDismiss() }
                            .onFailure { error = it.message ?: "Couldn't delete your chats. Please try again." }
                    }
                }) { Text("Delete", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancel") } },
        )
    }
}
