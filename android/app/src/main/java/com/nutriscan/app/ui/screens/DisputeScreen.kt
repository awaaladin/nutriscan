package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.DisputeRequest
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import kotlinx.coroutines.launch

/** For manufacturers and brand owners who believe a product is being shown
 * unfairly (e.g. a rival mass-reporting it). Goes to the admin queue -- nothing
 * on the product changes until a person reviews it. */
@Composable
fun DisputeScreen(
    repository: NutriScanRepository,
    barcode: String,
    onBack: () -> Unit,
    onSubmitted: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var company by remember { mutableStateOf("") }
    var contact by remember { mutableStateOf("") }
    var nafdac by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("") }
    var isSubmitting by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    NsScreenScaffold(title = "Manufacturer dispute", onBack = onBack) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp).verticalScroll(rememberScrollState()),
        ) {
            Text(
                "Own or make this product and think it's being shown unfairly? Tell us and we'll review it. " +
                    "Include your NAFDAC number so we can check it against the Greenbook.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(16.dp))
            OutlinedTextField(company, { company = it }, label = { Text("Company name") }, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(contact, { contact = it }, label = { Text("Email or phone we can reach you on") }, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(nafdac, { nafdac = it }, label = { Text("NAFDAC number (e.g. A4-1234)") }, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                message,
                { message = it.take(2000) },
                label = { Text("What's wrong, and what proof do you have?") },
                minLines = 4,
                modifier = Modifier.fillMaxWidth(),
            )
            error?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }
            Spacer(Modifier.height(16.dp))
            NsButton(
                enabled = !isSubmitting && company.isNotBlank() && contact.isNotBlank() && message.isNotBlank(),
                text = if (isSubmitting) "Sending…" else "Send dispute",
                onClick = {
                    isSubmitting = true
                    error = null
                    scope.launch {
                        repository.submitDispute(barcode, DisputeRequest(company, contact, message, nafdac))
                            .onSuccess { onSubmitted() }
                            .onFailure { error = if (it.message?.startsWith("Please check") == true) "Check the NAFDAC number format (e.g. A4-1234)." else it.message }
                        isSubmitting = false
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}
