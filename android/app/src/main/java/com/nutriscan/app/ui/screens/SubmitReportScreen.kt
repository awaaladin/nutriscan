package com.nutriscan.app.ui.screens

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.FilterChip
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsOutlinedButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

private const val MAX_PHOTOS = 4
private const val MAX_EDGE_PX = 1600

/** Decodes the picked image, scales its longest edge down to MAX_EDGE_PX and
 * re-encodes as JPEG, keeping uploads comfortably under the server's 5MB
 * per-photo limit regardless of the phone's camera resolution. */
private fun copyDownscaled(context: Context, uri: Uri): File? {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
    if (bounds.outWidth <= 0) return null

    var sample = 1
    while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= MAX_EDGE_PX) sample *= 2
    val bitmap = context.contentResolver.openInputStream(uri)?.use {
        BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample })
    } ?: return null

    val file = File(context.cacheDir, "report_${System.nanoTime()}.jpg")
    file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, 85, it) }
    bitmap.recycle()
    return file
}

@Composable
fun SubmitReportScreen(
    repository: NutriScanRepository,
    barcode: String,
    onBack: () -> Unit,
    onSubmitted: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var verdict by remember { mutableStateOf<String?>(null) }
    var comment by remember { mutableStateOf("") }
    var whereBought by remember { mutableStateOf("") }
    var batch by remember { mutableStateOf("") }
    var photos by remember { mutableStateOf(listOf<File>()) }
    var isSubmitting by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickMultipleVisualMedia(MAX_PHOTOS),
    ) { uris ->
        scope.launch {
            val copied = withContext(Dispatchers.IO) { uris.mapNotNull { copyDownscaled(context, it) } }
            photos = (photos + copied).take(MAX_PHOTOS)
        }
    }

    NsScreenScaffold(title = "Report this product", onBack = onBack) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp).verticalScroll(rememberScrollState()),
        ) {
            Text("Barcode: $barcode", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(12.dp))
            Text("Was the product you bought real or fake?", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            Row {
                FilterChip(selected = verdict == "real", onClick = { verdict = "real" }, label = { Text("Real") })
                Spacer(Modifier.width(8.dp))
                FilterChip(selected = verdict == "fake", onClick = { verdict = "fake" }, label = { Text("Fake") })
            }
            Spacer(Modifier.height(16.dp))
            OutlinedTextField(
                value = whereBought,
                onValueChange = { whereBought = it },
                label = { Text("Where did you buy it? (market, shop, city)") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = batch,
                onValueChange = { batch = it },
                label = { Text("Batch / lot number (optional)") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = comment,
                onValueChange = { comment = it.take(1000) },
                label = { Text("What made you think so? (packaging, taste, seal...)") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 3,
            )
            Spacer(Modifier.height(12.dp))
            Text(
                "Photos help others judge: ${photos.size}/$MAX_PHOTOS added. " +
                    "Show the packaging, seal and batch number.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(8.dp))
            Row {
                NsOutlinedButton(
                    text = "Add photos",
                    onClick = {
                        picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
                    },
                )
                if (photos.isNotEmpty()) {
                    Spacer(Modifier.width(8.dp))
                    NsOutlinedButton(text = "Clear", onClick = { photos = emptyList() })
                }
            }
            error?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }
            Spacer(Modifier.height(16.dp))
            Text(
                "Reports are public and reviewed if flagged. Only report your own experience, and only about authenticity.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))
            NsButton(
                enabled = !isSubmitting && verdict != null,
                text = if (isSubmitting) "Posting…" else "Post report",
                onClick = {
                    isSubmitting = true
                    error = null
                    scope.launch {
                        repository.submitReport(barcode, verdict.orEmpty(), comment, whereBought, batch, photos)
                            .onSuccess { onSubmitted() }
                            .onFailure { error = it.message }
                        isSubmitting = false
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}
