package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.WorkspacePremium
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.VerifyPurchaseRequest
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsGold500
import kotlinx.coroutines.launch

private val freeFeatures = listOf("Barcode scanning", "WHO health score", "Diabetic risk tier")
private val proFeatures = listOf("Personalized avoid-list", "Scan pattern tracking", "Priority product submissions")

@Composable
fun SubscriptionScreen(repository: NutriScanRepository, onBack: () -> Unit) {
    var isProcessing by remember { mutableStateOf(false) }
    var statusMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    NsScreenScaffold(
        title = "NutriScan Pro",
        onBack = onBack,
        actions = { Icon(Icons.Rounded.WorkspacePremium, contentDescription = null, tint = NsGold500) },
    ) { padding ->
    Column(modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp)) {
        FeatureCard(title = "Free", features = freeFeatures, highlighted = false)
        Spacer(Modifier.height(12.dp))
        FeatureCard(title = "Pro", features = proFeatures, highlighted = true)
        Spacer(Modifier.height(24.dp))
        androidx.compose.animation.AnimatedVisibility(
            visible = statusMessage != null,
            enter = androidx.compose.animation.fadeIn() + androidx.compose.animation.expandVertically(),
            exit = androidx.compose.animation.fadeOut(),
        ) {
            Column {
                Text(statusMessage ?: "", style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(12.dp))
            }
        }
        NsButton(
            enabled = !isProcessing,
            text = if (isProcessing) "Processing…" else "Upgrade — Monthly",
            onClick = {
                isProcessing = true
                scope.launch {
                    // TODO: replace with a real Google Play Billing purchase flow.
                    // This calls verify directly with a placeholder token for the MVP;
                    // see apps.subscriptions.views.VerifySubscriptionView on the backend.
                    val result = repository.verifySubscription(
                        VerifyPurchaseRequest(
                            plan = "monthly",
                            purchase_token = "placeholder-token",
                            product_id = "nutriscan_pro_monthly",
                        ),
                    )
                    isProcessing = false
                    result.onSuccess { statusMessage = "Pro active until ${it.expires_at}" }
                        .onFailure { statusMessage = it.message }
                }
            },
            modifier = Modifier.fillMaxWidth(),
        )
    }
    }
}

@Composable
private fun FeatureCard(title: String, features: List<String>, highlighted: Boolean) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (highlighted) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(12.dp))
            features.forEach { feature ->
                Row(modifier = Modifier.padding(vertical = 3.dp)) {
                    Icon(
                        Icons.Rounded.Check,
                        contentDescription = null,
                        tint = if (highlighted) NsGold500 else MaterialTheme.colorScheme.primary,
                        modifier = Modifier.height(20.dp),
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(feature, style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}
