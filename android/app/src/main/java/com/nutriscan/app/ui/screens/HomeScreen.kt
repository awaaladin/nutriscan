package com.nutriscan.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.outlined.EmojiEvents
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.rounded.QrCodeScanner
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.HealthLabelChip
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsOutlinedButton
import com.nutriscan.app.ui.theme.NsEmerald500
import com.nutriscan.app.ui.theme.NsEmerald900

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    repository: NutriScanRepository,
    onScan: () -> Unit,
    onOpenHistory: () -> Unit,
    onOpenProfile: () -> Unit,
    onOpenSubscription: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenInsights: () -> Unit,
    onOpenAchievements: () -> Unit,
    onOpenAlerts: () -> Unit,
) {
    val recentScans by repository.observeCachedScans().collectAsState(initial = emptyList())

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("NutriScan") },
                actions = {
                    IconButton(onClick = onOpenInsights) {
                        Icon(Icons.Outlined.Notifications, contentDescription = "Insights")
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Outlined.Settings, contentDescription = "Settings")
                    }
                },
            )
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    selected = true,
                    onClick = {},
                    label = { Text("Home") },
                    icon = { Icon(Icons.Filled.Home, contentDescription = null) },
                )
                NavigationBarItem(
                    selected = false,
                    onClick = onOpenHistory,
                    label = { Text("History") },
                    icon = { Icon(Icons.Outlined.History, contentDescription = null) },
                )
                NavigationBarItem(
                    selected = false,
                    onClick = onOpenAchievements,
                    label = { Text("Progress") },
                    icon = { Icon(Icons.Outlined.EmojiEvents, contentDescription = null) },
                )
                NavigationBarItem(
                    selected = false,
                    onClick = onOpenProfile,
                    label = { Text("Profile") },
                    icon = { Icon(Icons.Outlined.Person, contentDescription = null) },
                )
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(24.dp),
        ) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(28.dp),
                    colors = CardDefaults.cardColors(containerColor = Color.Transparent),
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Brush.linearGradient(listOf(NsEmerald900, NsEmerald500)))
                            .padding(24.dp),
                    ) {
                        Icon(
                            Icons.Rounded.QrCodeScanner,
                            contentDescription = null,
                            tint = Color.White,
                            modifier = Modifier.size(36.dp),
                        )
                        Spacer(Modifier.height(16.dp))
                        Text(
                            "Ready to check a product?",
                            style = MaterialTheme.typography.titleLarge,
                            color = Color.White,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            "Scan a barcode for an instant WHO health score.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color.White.copy(alpha = 0.85f),
                        )
                        Spacer(Modifier.height(20.dp))
                        NsButton(text = "Scan a product", onClick = onScan, modifier = Modifier.fillMaxWidth())
                    }
                }
                Spacer(Modifier.height(16.dp))
                NsOutlinedButton(
                    text = "Fake product alerts",
                    onClick = onOpenAlerts,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                NsOutlinedButton(
                    text = "Upgrade to Pro",
                    onClick = onOpenSubscription,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(28.dp))
                Text("Recent scans", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                if (recentScans.isEmpty()) {
                    Text(
                        "No scans yet. Scan a product to get started.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            items(recentScans) { scan ->
                Card(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    shape = RoundedCornerShape(16.dp),
                ) {
                    ListItem(
                        headlineContent = { Text(scan.productName) },
                        supportingContent = { HealthLabelChip(scan.label) },
                        trailingContent = {
                            Text("${scan.score}/10", style = MaterialTheme.typography.titleMedium)
                        },
                    )
                }
            }
        }
    }
}
