package com.nutriscan.app.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import coil.compose.AsyncImage
import com.nutriscan.app.ui.MAX_PRODUCT_PHOTOS
import com.nutriscan.app.ui.MIN_PRODUCT_PHOTOS
import com.nutriscan.app.ui.MainViewModel
import com.nutriscan.app.ui.ScanUiState
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsOutlinedButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsAmber
import com.nutriscan.app.ui.util.downscaleForUpload
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

private val sideLabels = listOf(
    "Front of the pack",
    "Back (nutrition table & NAFDAC number)",
    "A side or the top",
    "Another side",
    "Another side",
    "Another side",
)

/**
 * The one screen for photographing a product we don't know yet -- and for
 * retaking the photos when research fails. The photos are held in the ViewModel,
 * so after a failed attempt this screen reopens with the good ones still there
 * and only the bad ones need replacing.
 *
 * At least [MIN_PRODUCT_PHOTOS] sides are required: front for the name, back for
 * the nutrition table and NAFDAC number, a side to corroborate. All photos are
 * read by the AI in one request. [barcode] is null when none was scanned.
 */
@Composable
fun PhotoCaptureScreen(
    viewModel: MainViewModel,
    barcode: String?,
    onBack: () -> Unit,
    onSubmit: () -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()

    val photos by viewModel.photos.collectAsState()
    val scanState by viewModel.scanState.collectAsState()
    val lastFailure = (scanState as? ScanUiState.IdentifyFailed)?.message

    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED,
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        hasCameraPermission = it
    }
    LaunchedEffect(Unit) {
        if (!hasCameraPermission) permissionLauncher.launch(Manifest.permission.CAMERA)
    }

    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var retakeIndex by remember { mutableStateOf<Int?>(null) }
    var busy by remember { mutableStateOf(false) }
    var cameraError by remember { mutableStateOf<String?>(null) }
    var nafdac by remember { mutableStateOf("") }

    val nextIndex = retakeIndex ?: photos.size
    val canTakeMore = retakeIndex != null || photos.size < MAX_PRODUCT_PHOTOS

    fun takePhoto() {
        val capture = imageCapture ?: return
        if (busy || !canTakeMore) return
        busy = true
        val file = File(context.cacheDir, "product_${System.nanoTime()}.jpg")
        capture.takePicture(
            ImageCapture.OutputFileOptions.Builder(file).build(),
            ContextCompat.getMainExecutor(context),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                    scope.launch {
                        val small = withContext(Dispatchers.IO) { downscaleForUpload(file) }
                        val updated = viewModel.photos.value.toMutableList()
                        val index = retakeIndex
                        if (index != null && index in updated.indices) {
                            updated[index].delete()
                            updated[index] = small
                        } else if (updated.size < MAX_PRODUCT_PHOTOS) {
                            updated.add(small)
                        }
                        viewModel.setPhotos(updated)
                        retakeIndex = null
                        busy = false
                    }
                }

                override fun onError(exc: ImageCaptureException) {
                    cameraError = "The camera couldn't take that photo (${exc.message ?: "unknown error"}). Try again."
                    busy = false
                }
            },
        )
    }

    NsScreenScaffold(
        title = if (lastFailure != null) "Retake photos" else "Photograph the product",
        onBack = onBack,
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            // Why we're here again, in the server's own words.
            lastFailure?.let {
                Card(
                    colors = CardDefaults.cardColors(containerColor = NsAmber.copy(alpha = 0.15f)),
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text("The last attempt didn't work", style = MaterialTheme.typography.titleSmall)
                        Text(it, style = MaterialTheme.typography.bodySmall)
                        if (photos.isNotEmpty()) {
                            Text(
                                "Your photos are still here -- tap Retake on the unclear ones.",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
                Spacer(Modifier.height(12.dp))
            }

            Text(
                if (barcode != null) "Barcode $barcode isn't in our database yet." else "No barcode was scanned.",
                style = MaterialTheme.typography.titleSmall,
            )
            Text(
                "Take at least $MIN_PRODUCT_PHOTOS photos, one per side. We read them together to find the product, " +
                    "save its barcode and NAFDAC number, and check its authenticity -- once saved, scanning it again is instant.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))

            if (hasCameraPermission) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(280.dp)
                        .clip(RoundedCornerShape(16.dp)),
                ) {
                    AndroidView(
                        modifier = Modifier.fillMaxSize(),
                        factory = { ctx ->
                            val previewView = PreviewView(ctx)
                            val providerFuture = ProcessCameraProvider.getInstance(ctx)
                            providerFuture.addListener(
                                {
                                    val provider = providerFuture.get()
                                    val preview = Preview.Builder().build().also {
                                        it.setSurfaceProvider(previewView.surfaceProvider)
                                    }
                                    val capture = ImageCapture.Builder()
                                        .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                                        .build()
                                    try {
                                        provider.unbindAll()
                                        provider.bindToLifecycle(
                                            lifecycleOwner,
                                            CameraSelector.DEFAULT_BACK_CAMERA,
                                            preview,
                                            capture,
                                        )
                                        imageCapture = capture
                                    } catch (e: Exception) {
                                        cameraError = "The camera couldn't start (${e.message ?: "unknown error"})."
                                    }
                                },
                                ContextCompat.getMainExecutor(ctx),
                            )
                            previewView
                        },
                    )
                    Text(
                        if (canTakeMore) "Next: ${sideLabels[nextIndex.coerceAtMost(sideLabels.lastIndex)]}" else "Maximum photos reached",
                        color = Color.White,
                        style = MaterialTheme.typography.labelLarge,
                        modifier = Modifier
                            .align(Alignment.TopCenter)
                            .padding(10.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .border(BorderStroke(1.dp, Color.White.copy(alpha = 0.5f)), RoundedCornerShape(8.dp))
                            .padding(horizontal = 10.dp, vertical = 4.dp),
                    )
                }
                cameraError?.let {
                    Spacer(Modifier.height(4.dp))
                    Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
                Spacer(Modifier.height(8.dp))
                NsButton(
                    text = when {
                        busy -> "Saving photo…"
                        retakeIndex != null -> "Retake: ${sideLabels[retakeIndex!!.coerceAtMost(sideLabels.lastIndex)]}"
                        else -> "Take photo (${photos.size}/$MIN_PRODUCT_PHOTOS)"
                    },
                    enabled = !busy && canTakeMore && imageCapture != null,
                    onClick = { takePhoto() },
                    modifier = Modifier.fillMaxWidth(),
                )
            } else {
                Text(
                    "Camera permission is needed to photograph the product. Allow it in your phone's settings for NutriScan, then come back.",
                    color = MaterialTheme.colorScheme.error,
                )
                Spacer(Modifier.height(8.dp))
                NsOutlinedButton(
                    text = "Allow camera",
                    onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) },
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            if (photos.isNotEmpty()) {
                Spacer(Modifier.height(12.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    itemsIndexed(photos, key = { _, file -> file.absolutePath }) { index, file ->
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            AsyncImage(
                                model = file,
                                contentDescription = sideLabels[index.coerceAtMost(sideLabels.lastIndex)],
                                contentScale = ContentScale.Crop,
                                modifier = Modifier
                                    .size(92.dp)
                                    .clip(RoundedCornerShape(12.dp))
                                    .border(
                                        BorderStroke(
                                            if (retakeIndex == index) 3.dp else 1.dp,
                                            if (retakeIndex == index) NsAmber else Color.Gray.copy(alpha = 0.4f),
                                        ),
                                        RoundedCornerShape(12.dp),
                                    ),
                            )
                            Text("${index + 1}. " + sideLabels[index.coerceAtMost(sideLabels.lastIndex)].substringBefore(" ("), style = MaterialTheme.typography.labelSmall)
                            Row {
                                TextButton(onClick = { retakeIndex = if (retakeIndex == index) null else index }) {
                                    Text(if (retakeIndex == index) "Cancel" else "Retake", style = MaterialTheme.typography.labelSmall)
                                }
                                TextButton(onClick = {
                                    val updated = photos.toMutableList()
                                    updated.removeAt(index).delete()
                                    viewModel.setPhotos(updated)
                                    retakeIndex = null
                                }) { Text("Remove", style = MaterialTheme.typography.labelSmall) }
                            }
                        }
                    }
                }
            }

            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = nafdac,
                onValueChange = { nafdac = it },
                label = { Text("NAFDAC number (optional, e.g. A4-1234)") },
                supportingText = { Text("If we already know this number, we skip the AI and answer instantly.") },
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(12.dp))
            val missing = MIN_PRODUCT_PHOTOS - photos.size
            NsButton(
                text = if (missing > 0) "Take $missing more photo${if (missing == 1) "" else "s"} to continue" else "Research this product",
                enabled = missing <= 0 && !busy,
                onClick = {
                    viewModel.researchFromPhotos(barcode, nafdac.trim().ifBlank { null })
                    onSubmit()
                },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.width(1.dp))
            Spacer(Modifier.height(24.dp))
        }
    }
}
