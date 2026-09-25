package com.nutriscan.app.data.repository

import com.nutriscan.app.data.local.CachedScanDao
import com.nutriscan.app.data.local.CachedScanEntity
import com.nutriscan.app.data.local.SessionManager
import com.nutriscan.app.data.model.HistoryItem
import com.nutriscan.app.data.model.LoginRequest
import com.nutriscan.app.data.model.PreferencesUpdateRequest
import com.nutriscan.app.data.model.ProInsights
import com.nutriscan.app.data.model.ProductSubmissionRequest
import com.nutriscan.app.data.model.RegisterRequest
import com.nutriscan.app.data.model.RegisterResponse
import com.nutriscan.app.data.model.ScanRequest
import com.nutriscan.app.data.model.ScanResponse
import com.nutriscan.app.data.model.SubscriptionStatus
import com.nutriscan.app.data.model.TokenPair
import com.nutriscan.app.data.model.UserPreferences
import com.nutriscan.app.data.model.VerifyPurchaseRequest
import com.nutriscan.app.data.remote.ApiService
import kotlinx.coroutines.flow.Flow
import java.io.IOException

sealed class ScanOutcome {
    data class Success(val result: ScanResponse) : ScanOutcome()
    data class NotFound(val barcode: String) : ScanOutcome()
    data class OfflineCached(val cached: CachedScanEntity) : ScanOutcome()
    data class Error(val message: String) : ScanOutcome()
}

class NutriScanRepository(
    private val api: ApiService,
    private val cachedScanDao: CachedScanDao,
    private val sessionManager: SessionManager,
) {
    val isLoggedIn: Flow<Boolean> = sessionManager.isLoggedInFlow

    suspend fun register(request: RegisterRequest): Result<RegisterResponse> = runCatching {
        val response = api.register(request)
        if (!response.isSuccessful) error("Registration failed (${response.code()})")
        val body = requireNotNull(response.body())
        sessionManager.saveTokens(body.access, body.refresh)
        body
    }

    suspend fun login(username: String, password: String): Result<TokenPair> = runCatching {
        val response = api.login(LoginRequest(username, password))
        if (!response.isSuccessful) error("Login failed (${response.code()})")
        val body = requireNotNull(response.body())
        sessionManager.saveTokens(body.access, body.refresh)
        body
    }

    suspend fun logout() = sessionManager.clear()

    /** Scans a barcode against the backend. Falls back to the last cached
     * result for that barcode when the device is offline. */
    suspend fun scan(barcode: String): ScanOutcome = try {
        val response = api.scan(ScanRequest(barcode))
        when {
            response.isSuccessful -> {
                val body = requireNotNull(response.body())
                cachedScanDao.upsert(
                    CachedScanEntity(
                        barcode = barcode,
                        productName = body.product.name,
                        brand = body.product.brand,
                        score = body.score,
                        label = body.label,
                        diabeticRisk = body.diabetic_risk,
                        explanation = body.explanation,
                        scannedAtEpochMs = System.currentTimeMillis(),
                    ),
                )
                ScanOutcome.Success(body)
            }
            response.code() == 404 -> ScanOutcome.NotFound(barcode)
            else -> ScanOutcome.Error("Scan failed (${response.code()})")
        }
    } catch (e: IOException) {
        val cached = cachedScanDao.getByBarcode(barcode)
        if (cached != null) {
            ScanOutcome.OfflineCached(cached)
        } else {
            ScanOutcome.Error("You're offline and this product hasn't been scanned before.")
        }
    }

    fun observeCachedScans(): Flow<List<CachedScanEntity>> = cachedScanDao.observeAll()

    suspend fun history(): Result<List<HistoryItem>> = runCatching {
        val response = api.getHistory()
        if (!response.isSuccessful) error("Failed to load history (${response.code()})")
        requireNotNull(response.body())
    }

    suspend fun getPreferences(): Result<UserPreferences> = runCatching {
        val response = api.getPreferences()
        if (!response.isSuccessful) error("Failed to load preferences (${response.code()})")
        requireNotNull(response.body())
    }

    suspend fun updatePreferences(update: PreferencesUpdateRequest): Result<UserPreferences> = runCatching {
        val response = api.updatePreferences(update)
        if (!response.isSuccessful) error("Failed to update preferences (${response.code()})")
        requireNotNull(response.body())
    }

    suspend fun submitProduct(request: ProductSubmissionRequest): Result<Unit> = runCatching {
        val response = api.submitProduct(request)
        if (!response.isSuccessful) error("Submission failed (${response.code()})")
    }

    suspend fun verifySubscription(request: VerifyPurchaseRequest): Result<SubscriptionStatus> = runCatching {
        val response = api.verifySubscription(request)
        if (!response.isSuccessful) error("Verification failed (${response.code()})")
        requireNotNull(response.body())
    }

    suspend fun proInsights(): Result<ProInsights> = runCatching {
        val response = api.getProInsights()
        if (!response.isSuccessful) error("Failed to load insights (${response.code()})")
        requireNotNull(response.body())
    }
}
