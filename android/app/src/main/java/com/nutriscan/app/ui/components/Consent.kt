package com.nutriscan.app.ui.components

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

/** Where NutriScan's legal pages live (the public website). */
object Legal {
    private const val SITE = "https://nutriscan-download.vercel.app"
    const val TERMS = "$SITE/terms"
    const val PRIVACY = "$SITE/privacy"
    const val SAFETY = "$SITE/safety"
}

fun Context.openUrl(url: String) {
    try {
        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    } catch (_: ActivityNotFoundException) {
        // No browser installed: nothing more we can do.
    }
}

/** The two separate agreements sign-up needs: the Terms and Privacy Policy, and the explicit
 * consent Nigeria's Data Protection Act requires before health information is processed. */
@Composable
fun ConsentChecks(
    acceptTerms: Boolean,
    onAcceptTerms: (Boolean) -> Unit,
    healthConsent: Boolean,
    onHealthConsent: (Boolean) -> Unit,
    textColor: Color = MaterialTheme.colorScheme.onSurface,
    accent: Color = MaterialTheme.colorScheme.primary,
) {
    val context = LocalContext.current
    val colors = CheckboxDefaults.colors(checkedColor = accent, uncheckedColor = textColor.copy(alpha = 0.7f))
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = acceptTerms, onCheckedChange = onAcceptTerms, colors = colors)
            Text("I agree to the Terms of Use and Privacy Policy.", color = textColor, style = MaterialTheme.typography.bodySmall)
        }
        Row(modifier = Modifier.padding(start = 40.dp)) {
            TextButton(onClick = { context.openUrl(Legal.TERMS) }) { Text("Read the Terms", color = accent) }
            TextButton(onClick = { context.openUrl(Legal.PRIVACY) }) { Text("Read the Privacy Policy", color = accent) }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = healthConsent, onCheckedChange = onHealthConsent, colors = colors)
            Text(
                "I consent to NutriScan using the health information I give it (such as diabetes, blood pressure, " +
                    "readings and notes) to personalise my results and AI answers. I can delete it at any time.",
                color = textColor,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

/** Shown once to accounts created before consent was recorded. */
@Composable
fun ConsentDialog(onAgree: () -> Unit, onLogOut: () -> Unit) {
    var acceptTerms by remember { mutableStateOf(false) }
    var healthConsent by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = {},
        title = { Text("Updated Terms and Privacy Policy") },
        text = {
            Column(modifier = Modifier.fillMaxWidth()) {
                Text(
                    "To keep using NutriScan, please agree to our Terms and Privacy Policy and confirm how we may use " +
                        "your health information. NutriScan gives general information, not medical advice.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                ConsentChecks(acceptTerms, { acceptTerms = it }, healthConsent, { healthConsent = it })
            }
        },
        confirmButton = {
            TextButton(enabled = acceptTerms && healthConsent, onClick = onAgree) { Text("Agree and continue") }
        },
        dismissButton = { TextButton(onClick = onLogOut) { Text("Log out") } },
    )
}
