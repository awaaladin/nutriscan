package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.EmojiEvents
import androidx.compose.material.icons.rounded.LocalFireDepartment
import androidx.compose.material.icons.rounded.Spa
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material.icons.rounded.WorkspacePremium
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.local.CachedScanEntity
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsGold500
import java.util.concurrent.TimeUnit

private data class Badge(
    val icon: ImageVector,
    val title: String,
    val description: String,
    val unlocked: Boolean,
)

private fun currentStreakDays(scans: List<CachedScanEntity>): Int {
    if (scans.isEmpty()) return 0
    val dayMillis = TimeUnit.DAYS.toMillis(1)
    val scannedDays = scans.map { it.scannedAtEpochMs / dayMillis }.toSortedSet().toList().asReversed()
    val today = System.currentTimeMillis() / dayMillis
    if (scannedDays.first() < today - 1) return 0
    var streak = 1
    var expected = scannedDays.first() - 1
    for (day in scannedDays.drop(1)) {
        if (day == expected) {
            streak++
            expected--
        } else if (day < expected) {
            break
        }
    }
    return streak
}

private fun buildBadges(scans: List<CachedScanEntity>): List<Badge> {
    val total = scans.size
    val goodCount = scans.count { it.label == "Good" }
    val avoidRiskCount = scans.count { it.diabeticRisk == "Avoid" }
    val streak = currentStreakDays(scans)

    return listOf(
        Badge(Icons.Rounded.Verified, "First Scan", "Scan your first product", total >= 1),
        Badge(Icons.Rounded.Spa, "Health Explorer", "Scan 10 products", total >= 10),
        Badge(Icons.Rounded.WorkspacePremium, "Century Club", "Scan 100 products", total >= 100),
        Badge(Icons.Rounded.EmojiEvents, "Clean Eater", "Find 10 products rated Good", goodCount >= 10),
        Badge(Icons.Rounded.LocalFireDepartment, "3-Day Streak", "Scan on 3 days in a row", streak >= 3),
        Badge(Icons.Rounded.Verified, "Sugar Aware", "Catch 5 high diabetic-risk products before buying", avoidRiskCount >= 5),
    )
}

@Composable
fun AchievementsScreen(repository: NutriScanRepository, onBack: () -> Unit) {
    val scans by repository.observeCachedScans().collectAsState(initial = emptyList())
    val badges = buildBadges(scans)
    val streak = currentStreakDays(scans)

    NsScreenScaffold(title = "Your progress", onBack = onBack) { padding ->
    Column(modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp)) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
        ) {
            Row(modifier = Modifier.fillMaxWidth().padding(20.dp)) {
                StatBlock("Scans", scans.size.toString())
                StatBlock("Day streak", streak.toString())
                StatBlock("Badges", "${badges.count { it.unlocked }}/${badges.size}")
            }
        }
        Spacer(Modifier.height(24.dp))
        Text("Badges", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        LazyColumn {
            items(badges) { badge ->
                Card(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    shape = RoundedCornerShape(16.dp),
                ) {
                    Row(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            badge.icon,
                            contentDescription = null,
                            tint = if (badge.unlocked) NsGold500 else MaterialTheme.colorScheme.outline,
                            modifier = Modifier.size(32.dp),
                        )
                        Spacer(Modifier.width(16.dp))
                        Column {
                            Text(
                                badge.title,
                                style = MaterialTheme.typography.titleMedium,
                                color = if (badge.unlocked) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.outline,
                            )
                            Text(
                                badge.description,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }
    }
    }
}

@Composable
private fun StatBlock(label: String, value: String) {
    Column(modifier = Modifier.padding(end = 24.dp)) {
        Text(value, style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.onPrimaryContainer)
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onPrimaryContainer)
    }
}
