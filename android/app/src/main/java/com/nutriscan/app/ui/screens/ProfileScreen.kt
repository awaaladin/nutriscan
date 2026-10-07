package com.nutriscan.app.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Favorite
import androidx.compose.material.icons.rounded.MonitorHeart
import androidx.compose.material.icons.rounded.Person
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.PreferencesUpdateRequest
import com.nutriscan.app.data.model.UserPreferences
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsOutlinedButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsEmerald700
import com.nutriscan.app.ui.theme.NsGold500
import kotlinx.coroutines.launch

@Composable
fun ProfileScreen(repository: NutriScanRepository, onBack: () -> Unit) {
    var preferences by remember { mutableStateOf<UserPreferences?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var retryTick by remember { mutableIntStateOf(0) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(retryTick) {
        isLoading = true
        errorMessage = null
        val result = repository.getPreferences()
        isLoading = false
        result.onSuccess { preferences = it }.onFailure { errorMessage = it.message ?: "Couldn't load your profile." }
    }

    NsScreenScaffold(title = "Profile", onBack = onBack) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp)) {
            when {
                isLoading -> Column(
                    modifier = Modifier.fillMaxWidth().padding(top = 48.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    CircularProgressIndicator()
                }
                errorMessage != null -> AnimatedVisibility(visible = true, enter = fadeIn(), exit = fadeOut()) {
                    Column(
                        modifier = Modifier.fillMaxWidth().padding(top = 32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(errorMessage ?: "", color = MaterialTheme.colorScheme.error)
                        Spacer(Modifier.height(16.dp))
                        NsOutlinedButton(text = "Try again", onClick = { retryTick++ })
                    }
                }
                preferences != null -> {
                    val prefs = preferences!!
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier.size(56.dp).background(NsEmerald700, CircleShape),
                            contentAlignment = Alignment.Center,
                        ) {
                            Icon(Icons.Rounded.Person, contentDescription = null, tint = MaterialTheme.colorScheme.onPrimary)
                        }
                        Spacer(Modifier.width(16.dp))
                        Column {
                            Text(prefs.username ?: "", style = MaterialTheme.typography.titleLarge)
                            Text(
                                if (prefs.is_pro) "Pro member" else "Free plan",
                                style = MaterialTheme.typography.bodyMedium,
                                color = if (prefs.is_pro) NsGold500 else MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    Spacer(Modifier.height(28.dp))
                    Text("Health profile", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(8.dp))
                    Card(shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors()) {
                        Column {
                            SettingToggle(Icons.Rounded.Favorite, "Diabetic", prefs.is_diabetic) { newValue ->
                                scope.launch {
                                    repository.updatePreferences(PreferencesUpdateRequest(is_diabetic = newValue))
                                        .onSuccess { preferences = it }
                                }
                            }
                            SettingToggle(Icons.Rounded.MonitorHeart, "Hypertension", prefs.has_hypertension) { newValue ->
                                scope.launch {
                                    repository.updatePreferences(PreferencesUpdateRequest(has_hypertension = newValue))
                                        .onSuccess { preferences = it }
                                }
                            }
                        }
                    }
                    Spacer(Modifier.height(16.dp))
                    Text("Region: ${prefs.region}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun SettingToggle(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(16.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.width(12.dp))
            Text(label)
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}
