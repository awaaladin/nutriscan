package com.nutriscan.app.ui.screens

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
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
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.nutriscan.app.billing.PlayBilling
import com.nutriscan.app.billing.PlayPurchase
import com.nutriscan.app.billing.ProPlan
import com.nutriscan.app.billing.ProProducts
import com.nutriscan.app.billing.PurchaseEvent
import com.nutriscan.app.data.model.VerifyPurchaseRequest
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsGold500

private val freeFeatures = listOf("Barcode scanning", "WHO health score", "Diabetic risk tier")
private val proFeatures = listOf("Personalized avoid-list", "Scan pattern tracking", "Priority product submissions")

@Composable
fun SubscriptionScreen(repository: NutriScanRepository, onBack: () -> Unit) {
    val context = LocalContext.current
    val billing = remember { PlayBilling(context) }
    var plans by remember { mutableStateOf<List<ProPlan>>(emptyList()) }
    var isProcessing by remember { mutableStateOf(false) }
    var billingUnavailable by remember { mutableStateOf(false) }
    var statusMessage by remember { mutableStateOf<String?>(null) }

    suspend fun verify(purchase: PlayPurchase) {
        isProcessing = true
        repository.verifySubscription(VerifyPurchaseRequest(purchase.token, purchase.productId))
            .onSuccess { statusMessage = "Pro is active until ${it.expires_at?.take(10)}." }
            .onFailure { statusMessage = it.message }
        isProcessing = false
    }

    LaunchedEffect(Unit) {
        if (!billing.connect()) {
            billingUnavailable = true
            return@LaunchedEffect
        }
        plans = billing.loadPlans()
        // Restore: a reinstall or new phone still has the subscription in Play.
        billing.ownedPurchases().firstOrNull()?.let { verify(it) }
    }
    LaunchedEffect(Unit) {
        billing.events.collect { event ->
            when (event) {
                is PurchaseEvent.Purchased -> verify(event.purchase)
                PurchaseEvent.Pending -> statusMessage = "Your payment is pending. Pro turns on once Google confirms it."
                PurchaseEvent.Cancelled -> statusMessage = null
                is PurchaseEvent.Failed -> statusMessage = event.message
            }
        }
    }
    DisposableEffect(Unit) { onDispose { billing.disconnect() } }

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
        statusMessage?.let {
            Text(it, style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(12.dp))
        }
        when {
            billingUnavailable -> Text(
                "Google Play isn't available on this device, so subscriptions can't be started here.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            plans.isEmpty() -> Text(
                "Loading plans…",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            else -> plans.forEach { plan ->
                val label = if (plan.productId == ProProducts.YEARLY) "Yearly" else "Monthly"
                NsButton(
                    enabled = !isProcessing,
                    text = if (isProcessing) "Processing…" else "Upgrade — $label (${plan.price})",
                    onClick = { context.findActivity()?.let { billing.launch(it, plan) } },
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
            }
        }
    }
    }
}

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
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
