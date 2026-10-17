package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.automirrored.outlined.VolumeUp
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.NotificationsActive
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.local.AppPreferencesManager
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsOutlinedButton
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

    NsScreenScaffold(title = "Settings", onBack = onBack) { padding ->
    Column(modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp)) {
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
            supportingContent = { Text("Version 0.1.0 · Educational insights, not medical advice") },
        )

        Spacer(Modifier.height(32.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
            NsOutlinedButton(
                text = "Log out",
                onClick = { scope.launch { repository.logout(); onLoggedOut() } },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
    }
}
