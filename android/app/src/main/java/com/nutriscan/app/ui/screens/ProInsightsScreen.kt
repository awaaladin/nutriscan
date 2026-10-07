package com.nutriscan.app.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Shield
import androidx.compose.material.icons.rounded.TrendingUp
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.ProInsights
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsOutlinedButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsGold500

@Composable
fun ProInsightsScreen(repository: NutriScanRepository, onBack: () -> Unit) {
    var insights by remember { mutableStateOf<ProInsights?>(null) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var retryTick by remember { mutableIntStateOf(0) }

    LaunchedEffect(retryTick) {
        isLoading = true
        errorMessage = null
        val result = repository.proInsights()
        isLoading = false
        result.onSuccess { insights = it }.onFailure { errorMessage = it.message ?: "Couldn't load Pro insights." }
    }

    NsScreenScaffold(title = "Pro insights", onBack = onBack) { padding ->
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
                insights != null -> {
                    val data = insights!!
                    Row {
                        Icon(Icons.Rounded.TrendingUp, contentDescription = null, tint = NsGold500)
                        Spacer(Modifier.width(8.dp))
                        Text("Patterns", style = MaterialTheme.typography.titleMedium)
                    }
                    Spacer(Modifier.height(8.dp))
                    if (data.patterns.isEmpty()) {
                        Text(
                            "Not enough scans yet to detect patterns.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        data.patterns.forEach { pattern ->
                            Card(
                                modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                                shape = RoundedCornerShape(14.dp),
                                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                            ) {
                                Text(pattern, modifier = Modifier.padding(14.dp), style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                    Spacer(Modifier.height(24.dp))
                    Row {
                        Icon(Icons.Rounded.Shield, contentDescription = null, tint = NsGold500)
                        Spacer(Modifier.width(8.dp))
                        Text("Foods to avoid", style = MaterialTheme.typography.titleMedium)
                    }
                    Spacer(Modifier.height(8.dp))
                    if (data.avoid_list.isEmpty()) {
                        Text(
                            "Nothing flagged for your profile yet.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        LazyColumn {
                            items(data.avoid_list) { product ->
                                ListItem(headlineContent = { Text(product.name) })
                            }
                        }
                    }
                }
            }
        }
    }
}
