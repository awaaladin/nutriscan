package com.nutriscan.app.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import android.util.Size
import android.view.MotionEvent
import androidx.camera.core.Camera
import androidx.camera.core.FocusMeteringAction
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.FlashOff
import androidx.compose.material.icons.rounded.FlashOn
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.nutriscan.app.scanner.BarcodeAnalyzer
import kotlinx.coroutines.delay
import java.util.concurrent.Executors
import com.nutriscan.app.ui.MainViewModel
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsOutlinedButton

@Composable
fun ScannerScreen(
    viewModel: MainViewModel,
    onBack: () -> Unit,
    onBarcodeCaptured: () -> Unit,
    onTakePhotos: () -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED,
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        hasCameraPermission = granted
    }
    LaunchedEffect(Unit) {
        if (!hasCameraPermission) permissionLauncher.launch(Manifest.permission.CAMERA)
    }

    var manualBarcode by remember { mutableStateOf("") }
    var hasHandledResult by remember { mutableStateOf(false) }
    var camera by remember { mutableStateOf<Camera?>(null) }
    var torchOn by remember { mutableStateOf(false) }
    var zoom by remember { mutableFloatStateOf(0f) }
    var showHelp by remember { mutableStateOf(false) }
    // Analysis runs off the main thread so a slow frame never freezes the preview.
    val analysisExecutor = remember { Executors.newSingleThreadExecutor() }
    DisposableEffect(Unit) { onDispose { analysisExecutor.shutdown() } }

    // If nothing has been read for a while, say how to get a read instead of leaving the user guessing.
    LaunchedEffect(hasCameraPermission, hasHandledResult) {
        showHelp = false
        if (hasCameraPermission && !hasHandledResult) {
            delay(8000)
            showHelp = true
        }
    }

    fun capture(barcode: String) {
        if (hasHandledResult || barcode.isBlank()) return
        hasHandledResult = true
        viewModel.onBarcodeScanned(barcode)
        onBarcodeCaptured()
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Box(modifier = Modifier.weight(1f)) {
            if (hasCameraPermission) {
                AndroidView(
                    modifier = Modifier.fillMaxSize(),
                    factory = { ctx ->
                        val previewView = PreviewView(ctx)
                        val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
                        cameraProviderFuture.addListener(
                            {
                                val cameraProvider = cameraProviderFuture.get()
                                val preview = Preview.Builder().build().also {
                                    it.setSurfaceProvider(previewView.surfaceProvider)
                                }
                                val analysis = ImageAnalysis.Builder()
                                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                                    // The default 640x480 can't resolve a small or curved barcode (e.g. on a
                                    // gum pack); 1080p can.
                                    .setResolutionSelector(
                                        ResolutionSelector.Builder()
                                            .setResolutionStrategy(
                                                ResolutionStrategy(
                                                    Size(1920, 1080),
                                                    ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER,
                                                ),
                                            )
                                            .build(),
                                    )
                                    .build()
                                    .also {
                                        it.setAnalyzer(
                                            analysisExecutor,
                                            BarcodeAnalyzer { barcode -> capture(barcode) },
                                        )
                                    }
                                try {
                                    cameraProvider.unbindAll()
                                    camera = cameraProvider.bindToLifecycle(
                                        lifecycleOwner,
                                        CameraSelector.DEFAULT_BACK_CAMERA,
                                        preview,
                                        analysis,
                                    )
                                } catch (_: Exception) {
                                    // Binding can fail on emulators without a camera; manual entry still works.
                                }
                            },
                            ContextCompat.getMainExecutor(ctx),
                        )
                        // Tap anywhere to focus there -- the biggest help with a small barcode.
                        previewView.setOnTouchListener { view, event ->
                            if (event.action == MotionEvent.ACTION_UP) {
                                val point = previewView.meteringPointFactory.createPoint(event.x, event.y)
                                camera?.cameraControl?.startFocusAndMetering(
                                    FocusMeteringAction.Builder(point, FocusMeteringAction.FLAG_AF).build(),
                                )
                                view.performClick()
                            }
                            true
                        }
                        previewView
                    },
                )
                Box(
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .padding(20.dp)
                        .background(Color.Black.copy(alpha = 0.35f), CircleShape),
                ) {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Rounded.ArrowBack,
                            contentDescription = "Back",
                            tint = Color.White,
                        )
                    }
                }
                Box(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(20.dp)
                        .background(Color.Black.copy(alpha = 0.35f), CircleShape),
                ) {
                    IconButton(onClick = {
                        torchOn = !torchOn
                        camera?.cameraControl?.enableTorch(torchOn)
                    }) {
                        Icon(
                            if (torchOn) Icons.Rounded.FlashOn else Icons.Rounded.FlashOff,
                            contentDescription = "Toggle flash",
                            tint = Color.White,
                        )
                    }
                }
                Box(
                    modifier = Modifier
                        .align(Alignment.Center)
                        .size(260.dp, 160.dp)
                        .border(
                            BorderStroke(2.dp, Color.White.copy(alpha = 0.85f)),
                            RoundedCornerShape(20.dp),
                        ),
                )
                Column(
                    modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 20.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    if (showHelp) {
                        Text(
                            "Still not reading? Hold the phone 15-25 cm away, keep it steady in good light, " +
                                "tap the barcode to focus, or zoom in. You can also type the number printed " +
                                "under the barcode below.",
                            color = Color.White,
                            style = MaterialTheme.typography.bodySmall,
                            textAlign = TextAlign.Center,
                            modifier = Modifier
                                .padding(horizontal = 24.dp)
                                .background(Color.Black.copy(alpha = 0.55f), RoundedCornerShape(12.dp))
                                .padding(10.dp),
                        )
                        Spacer(Modifier.height(8.dp))
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Zoom", color = Color.White.copy(alpha = 0.85f), style = MaterialTheme.typography.labelSmall)
                        Slider(
                            value = zoom,
                            onValueChange = {
                                zoom = it
                                camera?.cameraControl?.setLinearZoom(it)
                            },
                            modifier = Modifier.width(220.dp).padding(horizontal = 8.dp),
                        )
                    }
                    Text(
                        "Barcode won't scan?",
                        color = Color.White.copy(alpha = 0.85f),
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Spacer(Modifier.height(6.dp))
                    NsOutlinedButton(
                        text = "Take a photo instead",
                        onClick = {
                            viewModel.onNoBarcode()
                            onTakePhotos()
                        },
                    )
                }
            } else {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Camera permission is required to scan barcodes.")
                }
                Box(
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .padding(20.dp)
                        .background(Color.Black.copy(alpha = 0.08f), CircleShape),
                ) {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Back")
                    }
                }
            }
        }
        Column(modifier = Modifier.padding(16.dp)) {
            Row {
                OutlinedTextField(
                    value = manualBarcode,
                    onValueChange = { manualBarcode = it },
                    label = { Text("Enter barcode manually") },
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                NsButton(text = "Go", onClick = { capture(manualBarcode) }, modifier = Modifier.height(56.dp))
            }
        }
    }
}
