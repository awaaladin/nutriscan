package com.nutriscan.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.nutriscan.app.data.local.CachedScanEntity
import com.nutriscan.app.data.model.ScanResponse
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.data.repository.ScanOutcome
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.io.File

sealed class ScanUiState {
    data object Idle : ScanUiState()
    data object Loading : ScanUiState()
    data class Success(val result: ScanResponse) : ScanUiState()
    data class NotFound(val barcode: String) : ScanUiState()
    data class PhotoUnclear(val barcode: String) : ScanUiState()
    data class NonFood(val productName: String, val message: String) : ScanUiState()
    data class Offline(val cached: CachedScanEntity) : ScanUiState()
    data class Error(val message: String) : ScanUiState()
}

/** Holds the in-flight/last scan result so the Scanner, Product Detail and
 * Health Analysis screens can share it without re-fetching. */
class MainViewModel(private val repository: NutriScanRepository) : ViewModel() {
    private val _scanState = MutableStateFlow<ScanUiState>(ScanUiState.Idle)
    val scanState: StateFlow<ScanUiState> = _scanState

    /** [photoFile] is the frame captured at the moment the barcode was read.
     * If the barcode isn't in Open Food Facts or our own table, it's used as
     * a fallback to identify the product from the photo instead of sending
     * the user straight to manual entry. */
    fun onBarcodeScanned(barcode: String, photoFile: File? = null) {
        if (_scanState.value is ScanUiState.Loading) return
        viewModelScope.launch {
            _scanState.value = ScanUiState.Loading
            val outcome = repository.scan(barcode)
            val triedPhoto = outcome is ScanOutcome.NotFound && photoFile != null
            val resolved = if (triedPhoto) {
                repository.identifyProduct(barcode, photoFile!!)
            } else {
                outcome
            }
            _scanState.value = resolved.toUiState(triedPhoto)
        }
    }

    /** Entry point when the live barcode scanner never read anything at all --
     * the user chose to photograph the product directly instead of hunting
     * for an angle that scans. There's no barcode to fall back from, so this
     * skips straight to Gemini reading the photo (barcode included, if it's
     * visible in frame -- see apps.integrations.vision_identify). */
    fun onPhotoCapturedWithoutBarcode(photoFile: File) {
        if (_scanState.value is ScanUiState.Loading) return
        viewModelScope.launch {
            _scanState.value = ScanUiState.Loading
            val resolved = repository.identifyProduct(barcode = null, photoFile)
            _scanState.value = resolved.toUiState(triedPhoto = true)
        }
    }

    private fun ScanOutcome.toUiState(triedPhoto: Boolean): ScanUiState = when (this) {
        is ScanOutcome.Success -> ScanUiState.Success(result)
        is ScanOutcome.NonFood -> ScanUiState.NonFood(productName, message)
        // Only a photo attempt gets the "retake it" message -- a plain
        // NotFound with no photo to fall back on goes straight to manual entry.
        is ScanOutcome.NotFound -> if (triedPhoto) ScanUiState.PhotoUnclear(barcode) else ScanUiState.NotFound(barcode)
        is ScanOutcome.OfflineCached -> ScanUiState.Offline(cached)
        is ScanOutcome.Error -> ScanUiState.Error(message)
    }

    fun resetScanState() {
        _scanState.value = ScanUiState.Idle
    }

    class Factory(private val repository: NutriScanRepository) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = MainViewModel(repository) as T
    }
}
