package com.nutriscan.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Warning
import androidx.compose.material.icons.rounded.Cancel
import androidx.compose.material.icons.rounded.HelpOutline
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.nutriscan.app.ui.theme.NsAmber
import com.nutriscan.app.ui.theme.NsCharcoal400
import com.nutriscan.app.ui.theme.NsEmerald700
import com.nutriscan.app.ui.theme.NsRed

private data class LabelStyle(val color: Color, val icon: ImageVector)

private fun styleFor(label: String): LabelStyle = when (label) {
    "Good" -> LabelStyle(NsEmerald700, Icons.Rounded.CheckCircle)
    "Moderate" -> LabelStyle(NsAmber, Icons.Rounded.Warning)
    "Incomplete" -> LabelStyle(NsCharcoal400, Icons.Rounded.HelpOutline)
    else -> LabelStyle(NsRed, Icons.Rounded.Cancel)
}

@Composable
fun HealthLabelChip(label: String, modifier: Modifier = Modifier) {
    val style = styleFor(label)
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = modifier
            .background(style.color.copy(alpha = 0.12f), CircleShape)
            .padding(horizontal = 10.dp, vertical = 5.dp),
    ) {
        Icon(style.icon, contentDescription = null, tint = style.color, modifier = Modifier.size(16.dp))
        Text(
            "  $label",
            color = style.color,
            style = MaterialTheme.typography.labelMedium,
        )
    }
}
