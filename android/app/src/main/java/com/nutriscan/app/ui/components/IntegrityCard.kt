package com.nutriscan.app.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.Integrity
import com.nutriscan.app.ui.theme.NsAmber
import com.nutriscan.app.ui.theme.NsEmerald700
import com.nutriscan.app.ui.theme.NsRed

private fun integrityColor(percent: Int): Color = when {
    percent >= 70 -> NsEmerald700
    percent >= 40 -> NsAmber
    else -> NsRed
}

private fun integrityHeadline(percent: Int): String = when {
    percent >= 70 -> "Likely genuine"
    percent >= 40 -> "Unverified -- be careful"
    else -> "Likely fake or unreliable"
}

/** The headline trust signal for a product. Always shows how much evidence is
 * behind the number, because a percentage with no votes behind it is just the
 * barcode check and shouldn't read as a community verdict. */
@Composable
fun IntegrityCard(integrity: Integrity, modifier: Modifier = Modifier) {
    val color = integrityColor(integrity.percent)
    val votes = integrity.real_votes + integrity.fake_votes
    Card(shape = RoundedCornerShape(16.dp), modifier = modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("${integrity.percent}%", style = MaterialTheme.typography.headlineMedium, color = color)
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(integrityHeadline(integrity.percent), style = MaterialTheme.typography.titleMedium)
                    Text(
                        "Integrity score",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Spacer(Modifier.height(10.dp))
            LinearProgressIndicator(
                progress = { integrity.percent / 100f },
                color = color,
                modifier = Modifier.fillMaxWidth().height(8.dp),
            )
            Spacer(Modifier.height(10.dp))
            Text(
                when {
                    votes == 0 -> "No community reports yet -- this score is based on the barcode only."
                    else -> "${integrity.real_votes} say real, ${integrity.fake_votes} say fake " +
                        "(${integrity.confidence} confidence)"
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (!integrity.checksum_valid) {
                Spacer(Modifier.height(4.dp))
                Text(
                    "This barcode number is not a valid retail barcode.",
                    style = MaterialTheme.typography.bodySmall,
                    color = NsRed,
                )
            }
        }
    }
}
