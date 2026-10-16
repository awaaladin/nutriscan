package com.nutriscan.app.data.repository

import com.nutriscan.app.data.local.CachedScanDao
import com.nutriscan.app.data.local.CachedScanEntity
import com.nutriscan.app.data.local.SessionManager
import com.nutriscan.app.data.model.AlertItem
import com.nutriscan.app.data.model.DisputeRequest
import com.nutriscan.app.data.model.HistoryItem
import com.nutriscan.app.data.model.LoginRequest
import com.nutriscan.app.data.model.PreferencesUpdateRequest
import com.nutriscan.app.data.model.ProInsights
import com.nutriscan.app.data.model.ProductSubmissionRequest
import com.nutriscan.app.data.model.RegisterRequest
import com.nutriscan.app.data.model.RegisterResponse
import com.nutriscan.app.data.model.ReportsResponse
import com.nutriscan.app.data.model.SubmitReportResponse
import com.nutriscan.app.data.model.ScanRequest
import com.nutriscan.app.data.model.ScanResponse
import com.nutriscan.app.data.model.SubscriptionStatus
import com.nutriscan.app.data.model.TokenPair
import com.nutriscan.app.data.model.UserPreferences
import com.nutriscan.app.data.model.VerifyPurchaseRequest
import com.nutriscan.app.data.remote.ApiService
import com.nutriscan.app.data.remote.friendlyErrorMessage
import kotlinx.coroutines.flow.Flow
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.io.IOException

sealed class ScanOutcome {
    data class Success(val result: ScanResponse) : ScanOutcome()
    data class NonFood(val productName: String, val message: String) : ScanOutcome()
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
        if (!response.isSuccessful) {
            val message = if (response.code() == 400) "That username or email is already taken." else friendlyErrorMessage(response.code())
            error(message)
        }
        val body = requireNotNull(response.body())
        sessionManager.saveTokens(body.access, body.refresh)
        body
    }

    suspend fun login(username: String, password: String): Result<TokenPair> = runCatching {
        val response = api.login(LoginRequest(username, password))
        if (!response.isSuccessful) {
            val message = if (response.code() == 401) "Incorrect username or password." else friendlyErrorMessage(response.code())
            error(message)
        }
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
                if (body.product_type != null && body.product_type != "food") {
                    ScanOutcome.NonFood(body.product.name, body.detail.orEmpty())
                } else {
                    cachedScanDao.upsert(
                        CachedScanEntity(
                            barcode = barcode,
                            productName = body.product.name,
                            brand = body.product.brand,
                            score = requireNotNull(body.score),
                            label = requireNotNull(body.label),
                            diabeticRisk = requireNotNull(body.diabetic_risk),
                            explanation = body.explanation.orEmpty(),
                            scannedAtEpochMs = System.currentTimeMillis(),
                        ),
                    )
                    ScanOutcome.Success(body)
                }
            }
            response.code() == 404 -> ScanOutcome.NotFound(barcode)
            else -> ScanOutcome.Error(friendlyErrorMessage(response.code()))
        }
    } catch (e: IOException) {
        val cached = cachedScanDao.getByBarcode(barcode)
        if (cached != null) {
            ScanOutcome.OfflineCached(cached)
        } else {
            ScanOutcome.Error("You're offline and this product hasn't been scanned before.")
        }
    }

    /** Identifies a product from a photo via Gemini instead of asking the user
     * to type in nutrition facts by hand. [barcode] is the camera's live
     * reading when this is a fallback from [scan] coming back NotFound, or
     * null when the live scanner never read a barcode at all and the user
     * chose to photograph the product directly -- Gemini then reads the
     * barcode straight off the photo (see apps.integrations.vision_identify
     * server-side). Best-effort -- see ScanResponse.is_estimated. */
    suspend fun identifyProduct(barcode: String?, photoFile: File): ScanOutcome = try {
        val barcodePart = barcode?.takeIf { it.isNotBlank() }?.toRequestBody("text/plain".toMediaType())
        val imagePart = MultipartBody.Part.createFormData(
            "image",
            photoFile.name,
            photoFile.asRequestBody("image/jpeg".toMediaType()),
        )
        val response = api.identifyProduct(barcodePart, imagePart)
        when {
            response.isSuccessful -> {
                val body = requireNotNull(response.body())
                if (body.product_type != null && body.product_type != "food") {
                    ScanOutcome.NonFood(body.product.name, body.detail.orEmpty())
                } else if (body.score != null && body.label != null && body.diabetic_risk != null) {
                    // body.product.barcode is the one actually stored server-side --
                    // when [barcode] was null, that's either what Gemini read off the
                    // photo or a synthetic one, never the (absent) client value.
                    cachedScanDao.upsert(
                        CachedScanEntity(
                            barcode = body.product.barcode,
                            productName = body.product.name,
                            brand = body.product.brand,
                            score = body.score,
                            label = body.label,
                            diabeticRisk = body.diabetic_risk,
                            explanation = body.explanation.orEmpty(),
                            scannedAtEpochMs = System.currentTimeMillis(),
                        ),
                    )
                    ScanOutcome.Success(body)
                } else {
                    ScanOutcome.NotFound(barcode.orEmpty())
                }
            }
            response.code() == 404 -> ScanOutcome.NotFound(barcode.orEmpty())
            else -> ScanOutcome.Error(friendlyErrorMessage(response.code()))
        }
    } catch (e: IOException) {
        ScanOutcome.Error("You're offline, so NutriScan can't identify this product from a photo right now.")
    }

    suspend fun reports(barcode: String): Result<ReportsResponse> = runCatching {
        val response = api.getReports(barcode)
        if (!response.isSuccessful) error(friendlyErrorMessage(response.code()))
        requireNotNull(response.body())
    }

    suspend fun submitReport(
        barcode: String,
        verdict: String,
        comment: String,
        whereBought: String,
        batchNumber: String,
        nafdacNumber: String,
        photos: List<File>,
    ): Result<SubmitReportResponse> = runCatching {
        fun text(value: String) = value.toRequestBody("text/plain".toMediaType())
        val photoParts = photos.map {
            MultipartBody.Part.createFormData("photos", it.name, it.asRequestBody("image/jpeg".toMediaType()))
        }
        val response = api.submitReport(
            barcode, text(verdict), text(comment), text(whereBought), text(batchNumber), text(nafdacNumber), photoParts,
        )
        if (!response.isSuccessful) {
            val message = if (response.code() == 400) "Couldn't post that report -- check the NAFDAC number format (e.g. A4-1234) and your photos (max 4, under 5MB each)." else friendlyErrorMessage(response.code())
            error(message)
        }
        requireNotNull(response.body())
    }

    suspend fun alerts(): Result<List<AlertItem>> = runCatching {
        val response = api.getAlerts()
        if (!response.isSuccessful) error(friendlyErrorMessage(response.code()))
        requireNotNull(response.body())
    }

    suspend fun submitDispute(barcode: String, request: DisputeRequest): Result<Unit> = runCatching {
        val response = api.submitDispute(barcode, request)
        if (!response.isSuccessful) error(friendlyErrorMessage(response.code()))
    }

    suspend fun flagReport(reportId: Int, reason: String = ""): Result<Unit> = runCatching {
        val response = api.flagReport(reportId, mapOf("reason" to reason))
        if (response.code() == 400) error("You can't flag your own report.")
        if (!response.isSuccessful) error(friendlyErrorMessage(response.code()))
    }

    fun observeCachedScans(): Flow<List<CachedScanEntity>> = cachedScanDao.observeAll()

    suspend fun history(): Result<List<HistoryItem>> = runCatching {
        val response = api.getHistory()
        if (!response.isSuccessful) error(friendlyErrorMessage(response.code()))
        requireNotNull(response.body())
    }

    suspend fun getPreferences(): Result<UserPreferences> = runCatching {
        val response = api.getPreferences()
        if (!response.isSuccessful) error(friendlyErrorMessage(response.code()))
        requireNotNull(response.body())
    }

    suspend fun updatePreferences(update: PreferencesUpdateRequest): Result<UserPreferences> = runCatching {
        val response = api.updatePreferences(update)
        if (!response.isSuccessful) error(friendlyErrorMessage(response.code()))
        requireNotNull(response.body())
    }

    suspend fun submitProduct(request: ProductSubmissionRequest): Result<Unit> = runCatching {
        val response = api.submitProduct(request)
        if (!response.isSuccessful) error(friendlyErrorMessage(response.code()))
    }

    suspend fun verifySubscription(request: VerifyPurchaseRequest): Result<SubscriptionStatus> = runCatching {
        val response = api.verifySubscription(request)
        if (!response.isSuccessful) error(friendlyErrorMessage(response.code()))
        requireNotNull(response.body())
    }

    suspend fun proInsights(): Result<ProInsights> = runCatching {
        val response = api.getProInsights()
        if (!response.isSuccessful) error(friendlyErrorMessage(response.code()))
        requireNotNull(response.body())
    }
}
