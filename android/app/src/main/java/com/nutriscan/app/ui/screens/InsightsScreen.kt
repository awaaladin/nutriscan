package com.nutriscan.app.ui.screens

import androidx.compose.foundation.background
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
import androidx.compose.material.icons.outlined.Lightbulb
import androidx.compose.material.icons.rounded.Insights
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsAmber
import com.nutriscan.app.ui.theme.NsEmerald500
import com.nutriscan.app.ui.theme.NsEmerald900
import com.nutriscan.app.ui.theme.NsRed
import java.util.concurrent.TimeUnit

private val whoTips = listOf(
    "WHO recommends keeping free sugars under 10% of daily energy intake — under 5% for additional benefit.",
    "High sodium intake is linked to raised blood pressure. WHO advises under 2g of sodium (5g of salt) per day.",
    "Choosing whole grains over refined grains is one of WHO's core recommendations for reducing diet-related disease risk.",
    "Saturated fat intake above 10% of daily energy is associated with higher cardiovascular risk, per WHO guidance.",
)

@Composable
fun InsightsScreen(repository: NutriScanRepository, onBack: () -> Unit) {
    val scans by repository.observeCachedScans().collectAsState(initial = emptyList())
    val weekMillis = TimeUnit.DAYS.toMillis(7)
    val cutoff = System.currentTimeMillis() - weekMillis
    val thisWeek = scans.filter { it.scannedAtEpochMs >= cutoff }

    val good = scans.count { it.label == "Good" }
    val moderate = scans.count { it.label == "Moderate" }
    val avoid = scans.count { it.label == "Avoid" }

    NsScreenScaffold(title = "Insights", onBack = onBack) { padding ->
        LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp)) {
            item {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(
                            Brush.linearGradient(listOf(NsEmerald900, NsEmerald500)),
                            RoundedCornerShape(24.dp),
                        )
                        .padding(20.dp),
                ) {
                    Icon(Icons.Rounded.Insights, contentDescription = null, tint = Color.White, modifier = Modifier.size(32.dp))
                    Spacer(Modifier.height(12.dp))
                    Text(
                        if (thisWeek.isEmpty()) {
                            "No scans yet this week"
                        } else {
                            "${thisWeek.size} product${if (thisWeek.size == 1) "" else "s"} scanned this week"
                        },
                        style = MaterialTheme.typography.titleLarge,
                        color = Color.White,
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "Scan more to build a clearer picture of your habits.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color.White.copy(alpha = 0.85f),
                    )
                }
                Spacer(Modifier.height(16.dp))
                Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp)) {
                    Column(modifier = Modifier.padding(20.dp)) {
                        Text("Your scan ratio", style = MaterialTheme.typography.titleMedium)
                        Spacer(Modifier.height(12.dp))
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(10.dp)
                                .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(6.dp)),
                        ) {
                            listOf(good to NsEmerald500, moderate to NsAmber, avoid to NsRed)
                                .filter { (count, _) -> count > 0 }
                                .forEach { (count, color) ->
                                    Row(
                                        modifier = Modifier
                                            .weight(count.toFloat())
                                            .fillMaxSize()
                                            .background(color),
                                    ) {}
                                }
                        }
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "$good Good · $moderate Moderate · $avoid Avoid",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                Spacer(Modifier.height(24.dp))
                Text("From WHO guidance", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
            }
            items(whoTips) { tip ->
                Card(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                ) {
                    Row(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                        Icon(Icons.Outlined.Lightbulb, contentDescription = null, tint = NsAmber)
                        Spacer(Modifier.width(12.dp))
                        Text(tip, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
    }
}
