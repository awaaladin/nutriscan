package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.repository.NutriScanRepository

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    repository: NutriScanRepository,
    onScan: () -> Unit,
    onOpenHistory: () -> Unit,
    onOpenProfile: () -> Unit,
    onOpenSubscription: () -> Unit,
) {
    val recentScans by repository.observeCachedScans().collectAsState(initial = emptyList())

    Scaffold(
        topBar = { TopAppBar(title = { Text("NutriScan") }) },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(selected = true, onClick = {}, label = { Text("Home") }, icon = {})
                NavigationBarItem(selected = false, onClick = onOpenHistory, label = { Text("History") }, icon = {})
                NavigationBarItem(selected = false, onClick = onOpenProfile, label = { Text("Profile") }, icon = {})
            }
        },
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize().padding(24.dp)) {
            Button(onClick = onScan, modifier = Modifier.fillMaxWidth().height(56.dp)) {
                Text("Scan a product")
            }
            Spacer(Modifier.height(12.dp))
            OutlinedButton(onClick = onOpenSubscription, modifier = Modifier.fillMaxWidth()) {
                Text("Upgrade to Pro")
            }
            Spacer(Modifier.height(24.dp))
            Text("Recent scans", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            if (recentScans.isEmpty()) {
                Text("No scans yet. Scan a product to get started.")
            } else {
                LazyColumn {
                    items(recentScans) { scan ->
                        ListItem(
                            headlineContent = { Text(scan.productName) },
                            supportingContent = { Text("${scan.label} · score ${scan.score}/10") },
                        )
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}
