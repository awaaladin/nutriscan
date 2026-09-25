package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
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
import kotlinx.coroutines.launch

@Composable
fun SubscriptionScreen(repository: NutriScanRepository) {
    var isProcessing by remember { mutableStateOf(false) }
    var statusMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Text("NutriScan Pro", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(16.dp))
        Text("Free", style = MaterialTheme.typography.titleMedium)
        Text("• Barcode scanning\n• WHO health score\n• Diabetic risk tier")
        Spacer(Modifier.height(16.dp))
        Text("Pro", style = MaterialTheme.typography.titleMedium)
        Text("• Personalized avoid-list\n• Scan pattern tracking\n• Priority product submissions")
        Spacer(Modifier.height(24.dp))
        statusMessage?.let {
            Text(it)
            Spacer(Modifier.height(8.dp))
        }
        Button(
            enabled = !isProcessing,
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
        ) {
            Text(if (isProcessing) "Processing..." else "Upgrade — Monthly")
        }
    }
}
