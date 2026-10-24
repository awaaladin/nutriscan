package com.nutriscan.app.ui.screens

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
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
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.nutriscan.app.data.model.CheckoutRequest
import com.nutriscan.app.data.model.ProPlan
import com.nutriscan.app.data.repository.EmailRequiredException
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsGold500
import kotlinx.coroutines.launch
import java.util.Locale

private val freeFeatures = listOf("Barcode scanning", "WHO health score", "Diabetic risk tier")
private val proFeatures = listOf("Personalized avoid-list", "Scan pattern tracking", "Priority product submissions")

/** Pro is paid for on the web, not in the app: the button opens Paystack's checkout page in the
 * browser (card, bank transfer, USSD). When the user comes back, the app asks the server to
 * confirm the payment with Paystack; the webhook switches Pro on as well if they never return. */
@Composable
fun SubscriptionScreen(repository: NutriScanRepository, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var plans by remember { mutableStateOf<List<ProPlan>>(emptyList()) }
    var plansFailed by remember { mutableStateOf(false) }
    var isPro by remember { mutableStateOf(false) }
    var isProcessing by remember { mutableStateOf(false) }
    var statusMessage by remember { mutableStateOf<String?>(null) }
    // Saveable: Android may kill the app while the browser is open.
    var pendingReference by rememberSaveable { mutableStateOf<String?>(null) }
    var needsEmail by rememberSaveable { mutableStateOf(false) }
    var email by rememberSaveable { mutableStateOf("") }

    suspend fun loadPlans() {
        plansFailed = false
        repository.proPlans()
            .onSuccess { plans = it }
            .onFailure { plansFailed = true }
    }

    suspend fun checkPending() {
        val reference = pendingReference ?: return
        isProcessing = true
        repository.verifyPayment(reference)
            .onSuccess {
                when {
                    it.is_pro && it.status == "success" -> {
                        isPro = true
                        pendingReference = null
                        statusMessage = "Payment received. NutriScan Pro is active."
                    }
                    it.status == "failed" -> {
                        pendingReference = null
                        statusMessage = "That payment wasn't accepted. Contact support with reference $reference."
                    }
                    else -> statusMessage = "Payment not confirmed yet. If you paid, Pro switches on within a few minutes."
                }
            }
            .onFailure { statusMessage = it.message }
        isProcessing = false
    }

    fun pay(plan: ProPlan) {
        scope.launch {
            isProcessing = true
            statusMessage = null
            val request = CheckoutRequest(plan = plan.plan, email = email.trim().takeIf { needsEmail && it.isNotEmpty() })
            repository.startCheckout(request)
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
        repository.getPreferences().onSuccess { prefs ->
            isPro = prefs.is_pro
            needsEmail = prefs.email.isNullOrBlank()
        }
        loadPlans()
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
        modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(24.dp),
    ) {
        FeatureCard(title = "Free", features = freeFeatures, highlighted = false)
        Spacer(Modifier.height(12.dp))
        FeatureCard(title = "Pro", features = proFeatures, highlighted = true)
        Spacer(Modifier.height(24.dp))
        statusMessage?.let {
            Text(it, style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(12.dp))
        }
        when {
            isPro -> Text(
                "You're a Pro member. Paying again adds another period after your current one ends.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            pendingReference != null -> NsButton(
                enabled = !isProcessing,
                text = if (isProcessing) "Checking…" else "I've paid, check now",
                onClick = { scope.launch { checkPending() } },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        Spacer(Modifier.height(12.dp))
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
        when {
            plansFailed -> NsButton(
                text = "Couldn't load plans. Try again",
                onClick = { scope.launch { loadPlans() } },
                modifier = Modifier.fillMaxWidth(),
            )
            plans.isEmpty() -> Text("Loading plans…", color = MaterialTheme.colorScheme.onSurfaceVariant)
            else -> {
                plans.forEach { plan ->
                    NsButton(
                        enabled = !isProcessing && (!needsEmail || email.contains("@")),
                        text = if (isProcessing) "Please wait…" else "Pay ${naira(plan.price_ngn)}: ${plan.label}",
                        onClick = { pay(plan) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(8.dp))
                }
                Text(
                    "You'll pay securely on Paystack's website with card, bank transfer or USSD. " +
                        "Pro is prepaid and doesn't renew automatically.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
    }
}

private fun naira(amount: Int) = "₦" + String.format(Locale.US, "%,d", amount)

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
