package com.nutriscan.app.ui.screens

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.WorkspacePremium
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.nutriscan.app.data.model.CheckoutRequest
import com.nutriscan.app.data.model.PlansResponse
import com.nutriscan.app.data.model.TierInfo
import com.nutriscan.app.data.repository.EmailRequiredException
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.Legal
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.components.openUrl
import com.nutriscan.app.ui.theme.NsGold500
import kotlinx.coroutines.launch
import java.util.Locale

private val TIER_RANK = mapOf("free" to 0, "pro" to 1, "plus" to 2, "care" to 3)

/** NutriScan's plans, paid for on the web, not in the app: a button opens Paystack's checkout page
 * in the browser (card, bank transfer, USSD). When the user comes back, the app asks the server to
 * confirm the payment with Paystack; the webhook switches the plan on as well if they never return. */
@Composable
fun SubscriptionScreen(repository: NutriScanRepository, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var data by remember { mutableStateOf<PlansResponse?>(null) }
    var loadFailed by remember { mutableStateOf(false) }
    var yearly by rememberSaveable { mutableStateOf(false) }
    var isProcessing by remember { mutableStateOf(false) }
    var statusMessage by remember { mutableStateOf<String?>(null) }
    // Saveable: Android may kill the app while the browser is open.
    var pendingReference by rememberSaveable { mutableStateOf<String?>(null) }
    var needsEmail by rememberSaveable { mutableStateOf(false) }
    var email by rememberSaveable { mutableStateOf("") }

    suspend fun load() {
        loadFailed = false
        repository.plans().onSuccess { data = it }.onFailure { loadFailed = true }
    }

    suspend fun checkPending() {
        val reference = pendingReference ?: return
        isProcessing = true
        repository.verifyPayment(reference)
            .onSuccess {
                when (it.status) {
                    "success" -> {
                        pendingReference = null
                        statusMessage = "Payment received. Thank you!"
                        load()
                    }
                    "failed" -> {
                        pendingReference = null
                        statusMessage = "That payment wasn't accepted. Contact support with reference $reference."
                    }
                    else -> statusMessage = "Payment not confirmed yet. If you paid, it switches on within a few minutes."
                }
            }
            .onFailure { statusMessage = it.message }
        isProcessing = false
    }

    fun pay(request: CheckoutRequest) {
        scope.launch {
            isProcessing = true
            statusMessage = null
            val withEmail = request.copy(email = email.trim().takeIf { needsEmail && it.isNotEmpty() })
            repository.startCheckout(withEmail)
                .onSuccess { checkout ->
                    pendingReference = checkout.reference
                    try {
                        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(checkout.authorization_url)))
                        statusMessage = "Finish paying in your browser, then come back here."
                    } catch (_: ActivityNotFoundException) {
                        statusMessage = "No web browser found to open the payment page."
                    }
                }
                .onFailure {
                    if (it is EmailRequiredException) needsEmail = true
                    statusMessage = it.message
                }
            isProcessing = false
        }
    }

    LaunchedEffect(Unit) {
        repository.getPreferences().onSuccess { needsEmail = it.email.isNullOrBlank() }
        load()
    }

    // Coming back from the browser: confirm the payment that was just made.
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME && pendingReference != null) scope.launch { checkPending() }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    NsScreenScaffold(
        title = "NutriScan Pro",
        onBack = onBack,
        actions = { Icon(Icons.Rounded.WorkspacePremium, contentDescription = null, tint = NsGold500) },
    ) { padding ->
    Column(
        modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(20.dp),
    ) {
        val plans = data
        when {
            loadFailed -> NsButton(
                text = "Couldn't load plans. Try again",
                onClick = { scope.launch { load() } },
                modifier = Modifier.fillMaxWidth(),
            )
            plans == null -> Text("Loading plans…", color = MaterialTheme.colorScheme.onSurfaceVariant)
            else -> {
                val balance = plans.balance
                val current = balance.tier
                Text(
                    if (current == "free") "You're on the free plan" else "You're on NutriScan ${plans.tiers.first { it.tier == current }.label}",
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    "${balance.total_remaining} AI credits left · monthly credits renew ${balance.renews_on}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(12.dp))
                statusMessage?.let {
                    Text(it, style = MaterialTheme.typography.bodyMedium)
                    Spacer(Modifier.height(8.dp))
                }
                if (pendingReference != null) {
                    NsButton(
                        enabled = !isProcessing,
                        text = if (isProcessing) "Checking…" else "I've paid, check now",
                        onClick = { scope.launch { checkPending() } },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(12.dp))
                }
                if (needsEmail) {
                    OutlinedTextField(
                        value = email,
                        onValueChange = { email = it },
                        label = { Text("Email for your receipt") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(12.dp))
                }
                Row {
                    FilterChip(selected = !yearly, onClick = { yearly = false }, label = { Text("Monthly") })
                    Spacer(Modifier.width(8.dp))
                    FilterChip(selected = yearly, onClick = { yearly = true }, label = { Text("Yearly: 2 months free") })
                }
                Spacer(Modifier.height(8.dp))
                val canPay = !isProcessing && (!needsEmail || email.contains("@"))
                plans.tiers.forEach { tier ->
                    TierCard(
                        tier = tier,
                        yearly = yearly,
                        isCurrent = tier.tier == current,
                        // A smaller plan can only be bought after the current one ends.
                        enabled = canPay && (TIER_RANK[tier.tier] ?: 0) >= (TIER_RANK[current] ?: 0),
                        onPay = { pay(CheckoutRequest(tier = tier.tier, plan = if (yearly) "yearly" else "monthly")) },
                    )
                    Spacer(Modifier.height(12.dp))
                }
                Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Need more AI this month?", style = MaterialTheme.typography.titleSmall)
                        Text(
                            "${plans.topup.credits} extra credits that never expire, used after your monthly ones.",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Spacer(Modifier.height(8.dp))
                        OutlinedButton(enabled = canPay, onClick = { pay(CheckoutRequest(kind = "credits")) }) {
                            Text("Buy ${plans.topup.credits} credits for ${naira(plans.topup.price_ngn)}")
                        }
                    }
                }
                Spacer(Modifier.height(12.dp))
                Text(
                    "Free plan: scanning, health scores, the diabetic risk tier and ${plans.free_monthly_credits} AI credits a month. " +
                        "A chat answer uses 1 credit, with photos 2, a Research mode answer 10, a meal plan or report 3.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    "You pay securely on Paystack's website with card, bank transfer or USSD. Plans are prepaid and do not " +
                        "renew automatically. NutriScan gives general information, not medical advice.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Row {
                    TextButton(onClick = { context.openUrl(Legal.TERMS) }) { Text("Terms and refunds") }
                    TextButton(onClick = { context.openUrl(Legal.PRIVACY) }) { Text("Privacy") }
                }
            }
        }
    }
    }
}

private fun naira(amount: Int) = "₦" + String.format(Locale.US, "%,d", amount)

@Composable
private fun TierCard(tier: TierInfo, yearly: Boolean, isCurrent: Boolean, enabled: Boolean, onPay: () -> Unit) {
    val highlighted = tier.tier == "care"
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        border = if (isCurrent) BorderStroke(2.dp, NsGold500) else null,
        colors = CardDefaults.cardColors(
            containerColor = if (highlighted) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(tier.label, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                if (isCurrent) Text("Your plan", color = NsGold500, style = MaterialTheme.typography.labelMedium)
            }
            Text(
                if (yearly) "${naira(tier.yearly_ngn)} a year" else "${naira(tier.monthly_ngn)} a month",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
            )
            Text("${tier.monthly_credits} AI credits every month", style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.height(10.dp))
            tier.features.forEach { feature ->
                Row(modifier = Modifier.padding(vertical = 3.dp)) {
                    Icon(Icons.Rounded.Check, contentDescription = null, tint = NsGold500, modifier = Modifier.height(20.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(feature, style = MaterialTheme.typography.bodyMedium)
                }
            }
            Spacer(Modifier.height(12.dp))
            NsButton(
                enabled = enabled,
                text = when {
                    isCurrent -> "Add another ${if (yearly) "year" else "month"}"
                    else -> "Get ${tier.label}"
                },
                onClick = onPay,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}
