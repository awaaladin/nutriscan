package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.PreferencesUpdateRequest
import com.nutriscan.app.data.model.UserPreferences
import com.nutriscan.app.data.repository.NutriScanRepository
import kotlinx.coroutines.launch

@Composable
fun ProfileScreen(repository: NutriScanRepository) {
    var preferences by remember { mutableStateOf<UserPreferences?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        val result = repository.getPreferences()
        isLoading = false
        result.onSuccess { preferences = it }.onFailure { errorMessage = it.message }
    }

    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Text("Profile & health settings", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(16.dp))
        when {
            isLoading -> CircularProgressIndicator()
            errorMessage != null -> Text(errorMessage ?: "", color = MaterialTheme.colorScheme.error)
            preferences != null -> {
                val prefs = preferences!!
                SettingToggle("Diabetic", prefs.is_diabetic) { newValue ->
                    scope.launch {
                        repository.updatePreferences(PreferencesUpdateRequest(is_diabetic = newValue))
                            .onSuccess { preferences = it }
                    }
                }
                SettingToggle("Hypertension", prefs.has_hypertension) { newValue ->
                    scope.launch {
                        repository.updatePreferences(PreferencesUpdateRequest(has_hypertension = newValue))
                            .onSuccess { preferences = it }
                    }
                }
                Spacer(Modifier.height(16.dp))
                Text("Region: ${prefs.region}")
                Text("Plan: ${if (prefs.is_pro) "Pro" else "Free"}")
            }
        }
    }
}

@Composable
private fun SettingToggle(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label)
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}
