package com.nutriscan.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.nutriscan.app.data.local.CachedScanEntity
import com.nutriscan.app.data.model.HistoryItem
import com.nutriscan.app.data.model.ScanResponse
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.data.repository.ScanOutcome
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.io.File

/** Photos needed before we'll research an unknown product: one per side
 * (front, back, and a side) gives the AI the name, the nutrition/NAFDAC panel
 * and corroboration in a single read. */
const val MIN_PRODUCT_PHOTOS = 3
const val MAX_PRODUCT_PHOTOS = 6

sealed class ScanUiState {
    data object Idle : ScanUiState()

    /** [message] says what is actually happening right now, not a canned loop. */
    data class Loading(val message: String) : ScanUiState()
    data class Success(val result: ScanResponse) : ScanUiState()

    /** Not in our database: the app moves to the photo screen to research it. */
    data class NeedsPhotos(val barcode: String?) : ScanUiState()

    /** Photo research failed; [message] is the server's reason, [retake] whether new photos could fix it. */
    data class IdentifyFailed(val barcode: String?, val message: String, val retake: Boolean) : ScanUiState()
    data class NonFood(val productName: String, val message: String) : ScanUiState()
    data class Offline(val cached: CachedScanEntity) : ScanUiState()
    data class Error(val message: String) : ScanUiState()
}

/** Holds the in-flight/last scan result so the Scanner, Photo, Analyzing, Product
 * Detail and Health Analysis screens can share it without re-fetching. */
class MainViewModel(private val repository: NutriScanRepository) : ViewModel() {
    private val _scanState = MutableStateFlow<ScanUiState>(ScanUiState.Idle)
    val scanState: StateFlow<ScanUiState> = _scanState

    /** Photos taken so far for the product being researched. Kept here, not in
     * the photo screen, so a failed attempt keeps them: the retake screen only
     * replaces the bad ones instead of starting over. */
    private val _photos = MutableStateFlow<List<File>>(emptyList())
    val photos: StateFlow<List<File>> = _photos

    /** Set while a product's missing nutrition is being added, so a failed attempt's
     * "Retake" / "enter manually" lead back to the completion screens rather than the
     * new-product ones. */
    var completingBarcode: String? = null
        private set

    /** Adds the missing nutrition of [barcode] from the photos taken so far (of the nutrition table). */
    fun completeFromPhotos(barcode: String) = runCompletion(barcode, emptyMap(), _photos.value)

    /** Adds the missing nutrition of [barcode] from values the user typed ([fields]: name -> text). */
    fun completeWithValues(barcode: String, fields: Map<String, String>) = runCompletion(barcode, fields, emptyList())

    private fun runCompletion(barcode: String, fields: Map<String, String>, files: List<File>) {
        if (_scanState.value is ScanUiState.Loading) return
        completingBarcode = barcode
        viewModelScope.launch {
            _scanState.value = ScanUiState.Loading(
                if (files.isEmpty()) "Adding the nutrition values and re-scoring…"
                else "Reading the nutrition table from your photo… (this can take up to 30 seconds)",
            )
            val outcome = repository.completeProduct(barcode, fields, files)
            if (outcome is ScanOutcome.Success) {
                clearPhotos()
                completingBarcode = null
            }
            _scanState.value = outcome.toUiState(barcode)
        }
    }

    /** Step 1: look the barcode up in our database (and Open Food Facts). If it
     * isn't known anywhere, the state becomes [ScanUiState.NeedsPhotos] and the
     * app opens the photo screen -- no dead end, no manual form first. */
    fun onBarcodeScanned(barcode: String) {
        if (_scanState.value is ScanUiState.Loading) return
        completingBarcode = null
        clearPhotos()
        viewModelScope.launch {
            _scanState.value = ScanUiState.Loading("Checking our database for barcode $barcode…")
            _scanState.value = when (val outcome = repository.scan(barcode)) {
                is ScanOutcome.NotFound -> ScanUiState.NeedsPhotos(barcode)
                else -> outcome.toUiState()
            }
        }
    }

    /** The scanner never read a barcode (or the user chose to skip it): go
     * straight to the photo screen. The server reads the barcode off the photos. */
    fun onNoBarcode() {
        completingBarcode = null
        clearPhotos()
        _scanState.value = ScanUiState.NeedsPhotos(null)
    }

    fun setPhotos(files: List<File>) {
        _photos.value = files.take(MAX_PRODUCT_PHOTOS)
    }

    fun clearPhotos() {
        _photos.value = emptyList()
    }

    /** Step 2: research the product from its photos. The server answers from
     * its own data first (barcode, then [nafdacNumber]) and only then calls the
     * AI -- once, with all the photos. */
    fun researchFromPhotos(barcode: String?, nafdacNumber: String?) {
        if (_scanState.value is ScanUiState.Loading) return
        val files = _photos.value
        if (files.size < MIN_PRODUCT_PHOTOS) return
        viewModelScope.launch {
            _scanState.value = ScanUiState.Loading(
                "Checking our database, then reading ${files.size} photos with AI if it's new " +
                    "(this can take up to 30 seconds)…",
            )
            val outcome = repository.identifyProduct(barcode, nafdacNumber, files)
            if (outcome is ScanOutcome.Success) clearPhotos()
            _scanState.value = outcome.toUiState(barcode)
        }
    }

    private fun ScanOutcome.toUiState(barcode: String? = null): ScanUiState = when (this) {
        is ScanOutcome.Success -> ScanUiState.Success(result)
        is ScanOutcome.NonFood -> ScanUiState.NonFood(productName, message)
        is ScanOutcome.NotFound -> ScanUiState.NeedsPhotos(this.barcode.ifBlank { barcode })
        is ScanOutcome.IdentifyFailed -> ScanUiState.IdentifyFailed(this.barcode.ifBlank { barcode }, message, retake)
        is ScanOutcome.OfflineCached -> ScanUiState.Offline(cached)
        is ScanOutcome.Error -> ScanUiState.Error(message)
    }

    /** Opens a scan from the user's history in the full product screen. The
     * history row already carries the whole product and the score it got, so
     * nothing is fetched again. */
    fun openScan(item: HistoryItem) {
        _scanState.value = ScanUiState.Success(
            ScanResponse(
                product = item.product,
                scan_id = item.id,
                score = item.score,
                label = item.label,
                diabetic_risk = item.diabetic_risk,
                flags = item.flags,
                is_estimated = item.product.is_estimated,
                source = "database",
            ),
        )
    }

    fun resetScanState() {
        _scanState.value = ScanUiState.Idle
        completingBarcode = null
        clearPhotos()
    }

    class Factory(private val repository: NutriScanRepository) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = MainViewModel(repository) as T
    }
}
