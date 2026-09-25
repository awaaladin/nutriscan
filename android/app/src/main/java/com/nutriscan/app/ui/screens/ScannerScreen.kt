package com.nutriscan.app.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.nutriscan.app.scanner.BarcodeAnalyzer
import com.nutriscan.app.ui.MainViewModel
import com.nutriscan.app.ui.ScanUiState

@Composable
fun ScannerScreen(
    viewModel: MainViewModel,
    onProductFound: (barcode: String) -> Unit,
    onNotFound: (barcode: String) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scanState by viewModel.scanState.collectAsState()

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

    LaunchedEffect(scanState) {
        when (val state = scanState) {
            is ScanUiState.Success -> if (!hasHandledResult) {
                hasHandledResult = true
                onProductFound(state.result.product.barcode)
            }
            is ScanUiState.NotFound -> if (!hasHandledResult) {
                hasHandledResult = true
                onNotFound(state.barcode)
            }
            else -> Unit
        }
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
                                    .build()
                                    .also {
                                        it.setAnalyzer(
                                            ContextCompat.getMainExecutor(ctx),
                                            BarcodeAnalyzer { barcode ->
                                                if (!hasHandledResult) {
                                                    viewModel.onBarcodeScanned(barcode)
                                                }
                                            },
                                        )
                                    }
                                try {
                                    cameraProvider.unbindAll()
                                    cameraProvider.bindToLifecycle(
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
                        previewView
                    },
                )
            } else {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Camera permission is required to scan barcodes.")
                }
            }
            if (scanState is ScanUiState.Loading) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
        }
        Column(modifier = Modifier.padding(16.dp)) {
            if (scanState is ScanUiState.Error) {
                Text((scanState as ScanUiState.Error).message, color = MaterialTheme.colorScheme.error)
                Spacer(Modifier.height(8.dp))
            }
            Row {
                OutlinedTextField(
                    value = manualBarcode,
                    onValueChange = { manualBarcode = it },
                    label = { Text("Enter barcode manually") },
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                Button(onClick = {
                    hasHandledResult = false
                    viewModel.onBarcodeScanned(manualBarcode)
                }) {
                    Text("Go")
                }
            }
        }
    }
}
