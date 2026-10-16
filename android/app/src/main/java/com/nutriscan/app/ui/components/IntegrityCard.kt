package com.nutriscan.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Cancel
import androidx.compose.material.icons.rounded.HelpOutline
import androidx.compose.material.icons.rounded.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.Integrity
import com.nutriscan.app.ui.theme.NsAmber
import com.nutriscan.app.ui.theme.NsCharcoal400
import com.nutriscan.app.ui.theme.NsEmerald700
import com.nutriscan.app.ui.theme.NsRed

private data class TierStyle(val color: Color, val icon: ImageVector)

fun tierColor(tier: String): Color = tierStyle(tier).color

private fun tierStyle(tier: String): TierStyle = when (tier) {
    "verified" -> TierStyle(NsEmerald700, Icons.Rounded.CheckCircle)
    "reported_fake" -> TierStyle(NsRed, Icons.Rounded.Cancel)
    "disputed", "suspicious" -> TierStyle(NsAmber, Icons.Rounded.Warning)
    else -> TierStyle(NsCharcoal400, Icons.Rounded.HelpOutline)
}

/** The trust signal for a product. It shows a tier and the reasons behind it
 * rather than a percentage: no registry or vote count can prove one pack is
 * genuine, so the card says what we actually know and what we don't. */
@Composable
fun IntegrityCard(integrity: Integrity, modifier: Modifier = Modifier) {
    val style = tierStyle(integrity.tier)
    Card(shape = RoundedCornerShape(16.dp), modifier = modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(style.icon, contentDescription = null, tint = style.color, modifier = Modifier.size(28.dp))
                Spacer(Modifier.width(10.dp))
                Column {
                    Text(integrity.headline, style = MaterialTheme.typography.titleMedium, color = style.color)
                    Text(
                        "Authenticity check",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Spacer(Modifier.height(10.dp))
            integrity.reasons.forEach { reason ->
                Row(modifier = Modifier.padding(vertical = 2.dp), verticalAlignment = Alignment.Top) {
                    Spacer(Modifier.width(2.dp))
                    Spacer(
                        Modifier
                            .padding(top = 7.dp)
                            .size(5.dp)
                            .background(style.color, CircleShape),
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(reason, style = MaterialTheme.typography.bodySmall)
                }
            }
            Spacer(Modifier.height(8.dp))
            Text(
                "Based on a registry check and user reports. It can't prove an individual pack is genuine " +
                    "-- check the seal and batch number too.",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
