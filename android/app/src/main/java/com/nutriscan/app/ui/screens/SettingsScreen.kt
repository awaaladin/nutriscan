package com.nutriscan.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.automirrored.outlined.VolumeUp
import androidx.compose.material.icons.outlined.Gavel
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.PrivacyTip
import androidx.compose.material.icons.outlined.NotificationsActive
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TextButton
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.local.AppPreferencesManager
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.BuildConfig
import com.nutriscan.app.ui.components.Legal
import com.nutriscan.app.ui.components.NsOutlinedButton
import com.nutriscan.app.ui.components.openUrl
import com.nutriscan.app.ui.components.NsScreenScaffold
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(
    repository: NutriScanRepository,
    preferences: AppPreferencesManager,
    onBack: () -> Unit,
    onLoggedOut: () -> Unit,
) {
    val darkModeOverride by preferences.darkModeOverride.collectAsState(initial = null)
    val notificationsEnabled by preferences.notificationsEnabled.collectAsState(initial = true)
    val autoReadAloud by preferences.autoReadAloud.collectAsState(initial = false)
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var deleting by remember { mutableStateOf(false) }

    NsScreenScaffold(title = "Settings", onBack = onBack) { padding ->
    Column(modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(24.dp)) {
        ListItem(
            leadingContent = { Icon(Icons.Outlined.DarkMode, contentDescription = null) },
            headlineContent = { Text("Dark mode") },
            supportingContent = { Text(if (darkModeOverride == null) "Follow system" else if (darkModeOverride == true) "On" else "Off") },
            trailingContent = {
                Switch(
                    checked = darkModeOverride == true,
                    onCheckedChange = { checked ->
                        scope.launch { preferences.setDarkModeOverride(checked) }
                    },
                )
            },
        )
        HorizontalDivider()
        ListItem(
            leadingContent = { Icon(Icons.Outlined.NotificationsActive, contentDescription = null) },
            headlineContent = { Text("Notifications") },
            supportingContent = { Text("Insights and scan reminders") },
            trailingContent = {
                Switch(
                    checked = notificationsEnabled,
                    onCheckedChange = { checked ->
                        scope.launch { preferences.setNotificationsEnabled(checked) }
                    },
                )
            },
        )
        HorizontalDivider()
        ListItem(
            leadingContent = { Icon(Icons.AutoMirrored.Outlined.VolumeUp, contentDescription = null) },
            headlineContent = { Text("Read results aloud") },
            supportingContent = { Text("Speak scan results and answers automatically") },
            trailingContent = {
                Switch(
                    checked = autoReadAloud,
                    onCheckedChange = { checked ->
                        scope.launch { preferences.setAutoReadAloud(checked) }
                    },
                )
            },
        )
        HorizontalDivider()
        ListItem(
            leadingContent = { Icon(Icons.Outlined.Info, contentDescription = null) },
            headlineContent = { Text("About NutriScan") },
            supportingContent = { Text("Version ${BuildConfig.VERSION_NAME} · General information, not medical advice") },
        )
        HorizontalDivider()
        ListItem(
            modifier = Modifier.clickable { context.openUrl(Legal.TERMS) },
            leadingContent = { Icon(Icons.Outlined.Gavel, contentDescription = null) },
            headlineContent = { Text("Terms of Use") },
            supportingContent = { Text("Including subscriptions, credits and refunds") },
        )
        HorizontalDivider()
        ListItem(
            modifier = Modifier.clickable { context.openUrl(Legal.PRIVACY) },
            leadingContent = { Icon(Icons.Outlined.PrivacyTip, contentDescription = null) },
            headlineContent = { Text("Privacy Policy") },
            supportingContent = { Text("What we collect, why, and your rights") },
        )

        Spacer(Modifier.height(32.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
            NsOutlinedButton(
                text = "Log out",
                onClick = { scope.launch { repository.logout(); onLoggedOut() } },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        Spacer(Modifier.height(12.dp))
        TextButton(onClick = { deleting = true }, modifier = Modifier.fillMaxWidth()) {
            Text("Delete my account", color = MaterialTheme.colorScheme.error)
        }
    }
    }

    if (deleting) DeleteAccountDialog(repository, onDismiss = { deleting = false }, onDeleted = onLoggedOut)
}

/** Permanent erasure of the account and its personal data (the NDPA right to erasure). */
@Composable
private fun DeleteAccountDialog(repository: NutriScanRepository, onDismiss: () -> Unit, onDeleted: () -> Unit) {
    val scope = rememberCoroutineScope()
    var password by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Delete your account?") },
        text = {
            Column {
                Text(
                    "This permanently erases your profile, health notes and readings, chats, scans and reports. " +
                        "It can't be undone. Any remaining plan time or credits are lost. Payment records are kept, " +
                        "without your details, because the law requires it.",
                )
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = password, onValueChange = { password = it }, label = { Text("Your password") },
                    singleLine = true, visualTransformation = PasswordVisualTransformation(),
                )
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = {
            TextButton(enabled = password.isNotBlank() && !working, onClick = {
                working = true
                scope.launch {
                    repository.deleteAccount(password)
                        .onSuccess { onDeleted() }
                        .onFailure { error = it.message }
                    working = false
                }
            }) { Text(if (working) "Deleting…" else "Delete forever", color = MaterialTheme.colorScheme.error) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
