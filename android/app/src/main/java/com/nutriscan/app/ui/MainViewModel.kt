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

sealed class ScanUiState {
    data object Idle : ScanUiState()
    data object Loading : ScanUiState()
    data class Success(val result: ScanResponse) : ScanUiState()
    data class NotFound(val barcode: String) : ScanUiState()
    data class Offline(val cached: CachedScanEntity) : ScanUiState()
    data class Error(val message: String) : ScanUiState()
}

/** Holds the in-flight/last scan result so the Scanner, Product Detail and
 * Health Analysis screens can share it without re-fetching. */
class MainViewModel(private val repository: NutriScanRepository) : ViewModel() {
    private val _scanState = MutableStateFlow<ScanUiState>(ScanUiState.Idle)
    val scanState: StateFlow<ScanUiState> = _scanState

    fun onBarcodeScanned(barcode: String) {
        if (_scanState.value is ScanUiState.Loading) return
        viewModelScope.launch {
            _scanState.value = ScanUiState.Loading
            _scanState.value = when (val outcome = repository.scan(barcode)) {
                is ScanOutcome.Success -> ScanUiState.Success(outcome.result)
                is ScanOutcome.NotFound -> ScanUiState.NotFound(outcome.barcode)
                is ScanOutcome.OfflineCached -> ScanUiState.Offline(outcome.cached)
                is ScanOutcome.Error -> ScanUiState.Error(outcome.message)
            }
        }
    }

    fun resetScanState() {
        _scanState.value = ScanUiState.Idle
    }

    class Factory(private val repository: NutriScanRepository) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = MainViewModel(repository) as T
    }
}
