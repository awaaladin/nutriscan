package com.nutriscan.app.data.repository

import com.nutriscan.app.data.local.CachedScanDao
import com.nutriscan.app.data.local.CachedScanEntity
import com.nutriscan.app.data.local.SessionManager
import com.nutriscan.app.data.model.AlertItem
import com.nutriscan.app.data.model.AskRequest
import com.nutriscan.app.data.model.AskResponse
import com.nutriscan.app.data.model.AskTurn
import com.nutriscan.app.data.model.CorrectionRequest
import com.nutriscan.app.data.model.CorrectionResponse
import com.nutriscan.app.data.model.SearchResponse
import com.nutriscan.app.data.model.AssistantSettings
import com.nutriscan.app.data.model.ChatReply
import com.nutriscan.app.data.model.ChatThreadDetail
import com.nutriscan.app.data.model.ChatThreadSummary
import com.nutriscan.app.data.model.FeedbackRequest
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
import com.nutriscan.app.data.remote.describeFailure
import com.nutriscan.app.data.remote.friendlyErrorMessage
import com.nutriscan.app.data.remote.parseServerError
import kotlinx.coroutines.flow.Flow
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.io.IOException
import java.net.SocketTimeoutException

/** A failed assistant request. [notice] is the server's fixed safety message for
 * emergency-sounding questions; it must be shown even though the AI could not answer. */
class ChatException(message: String, val notice: String?) : Exception(message)

sealed class ScanOutcome {
    data class Success(val result: ScanResponse) : ScanOutcome()
    data class NonFood(val productName: String, val message: String) : ScanOutcome()
    data class NotFound(val barcode: String) : ScanOutcome()

    /** Photo research failed. [message] says why (from the server); [retake]
     * is true when better photos could fix it. */
    data class IdentifyFailed(val barcode: String, val message: String, val retake: Boolean) : ScanOutcome()
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
                            score = body.score ?: 0, // 0 = no score (label "Incomplete")
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
            else -> ScanOutcome.Error(describeFailure(response))
        }
    } catch (e: IOException) {
        val cached = cachedScanDao.getByBarcode(barcode)
        if (cached != null) {
            ScanOutcome.OfflineCached(cached)
        } else {
            ScanOutcome.Error("You're offline and this product hasn't been scanned before.")
        }
    }

    /** Researches a product that isn't in our database from photos of its sides.
     * The server checks its own data first (barcode, then [nafdacNumber]) and only
     * calls the AI if neither matches, saving the result so the next scan of this
     * barcode is instant. [barcode] is null when the live scanner never read one --
     * the server then reads it off the photos. */
    suspend fun identifyProduct(barcode: String?, nafdacNumber: String?, photos: List<File>): ScanOutcome = try {
        fun text(value: String?) = value?.takeIf { it.isNotBlank() }?.toRequestBody("text/plain".toMediaType())
        val parts = photos.map {
            MultipartBody.Part.createFormData("images", it.name, it.asRequestBody("image/jpeg".toMediaType()))
        }
        val response = api.identifyProduct(text(barcode), text(nafdacNumber), parts)
        when {
            response.isSuccessful -> {
                val body = requireNotNull(response.body())
                if (body.product_type != null && body.product_type != "food") {
                    ScanOutcome.NonFood(body.product.name, body.detail.orEmpty())
                } else if (body.label != null && body.diabetic_risk != null) {
                    // body.product.barcode is the one actually stored server-side --
                    // when [barcode] was null, that's what the AI read or a synthetic one.
                    cachedScanDao.upsert(
                        CachedScanEntity(
                            barcode = body.product.barcode,
                            productName = body.product.name,
                            brand = body.product.brand,
                            score = body.score ?: 0,
                            label = body.label,
                            diabeticRisk = body.diabetic_risk,
                            explanation = body.explanation.orEmpty(),
                            scannedAtEpochMs = System.currentTimeMillis(),
                        ),
                    )
                    ScanOutcome.Success(body)
                } else {
                    ScanOutcome.IdentifyFailed(
                        barcode.orEmpty(),
                        "The server returned an incomplete result for this product. Please retake the photos.",
                        retake = true,
                    )
                }
            }
            else -> {
                val error = parseServerError(response) // read once: the body can't be re-read
                ScanOutcome.IdentifyFailed(
                    barcode.orEmpty(),
                    describeFailure(response.code(), error),
                    // Without structured info, assume photos might help for a client error.
                    retake = error?.retake ?: (response.code() in 400..499),
                )
            }
        }
    } catch (e: SocketTimeoutException) {
        ScanOutcome.IdentifyFailed(
            barcode.orEmpty(),
            "The server is taking too long to research this product. Your connection may be slow -- " +
                "try again, or retake the photos so they upload faster.",
            retake = false,
        )
    } catch (e: IOException) {
        ScanOutcome.Error("No connection: the photos couldn't be sent. Check your internet and try again.")
    }

    /** Completes a product whose nutrition data is missing so it can be scored: from a
     * photo of the nutrition table, typed [fields] (field name -> text, e.g. "sugar_g"),
     * or both. The server only fills blanks, so nothing already on file is changed. */
    suspend fun completeProduct(barcode: String, fields: Map<String, String>, photos: List<File>): ScanOutcome = try {
        val textParts = fields.filterValues { it.isNotBlank() }
            .mapValues { it.value.toRequestBody("text/plain".toMediaType()) }
        val imageParts = photos.map {
            MultipartBody.Part.createFormData("images", it.name, it.asRequestBody("image/jpeg".toMediaType()))
        }
        val response = api.completeProduct(barcode, textParts, imageParts)
        if (response.isSuccessful) {
            val body = requireNotNull(response.body())
            if (body.label != null && body.diabetic_risk != null) {
                cachedScanDao.upsert(
                    CachedScanEntity(
                        barcode = body.product.barcode,
                        productName = body.product.name,
                        brand = body.product.brand,
                        score = body.score ?: 0,
                        label = body.label,
                        diabeticRisk = body.diabetic_risk,
                        explanation = body.explanation.orEmpty(),
                        scannedAtEpochMs = System.currentTimeMillis(),
                    ),
                )
                ScanOutcome.Success(body)
            } else {
                ScanOutcome.IdentifyFailed(barcode, "The server returned an incomplete result. Please try again.", retake = false)
            }
        } else {
            val error = parseServerError(response) // read once: the body can't be re-read
            ScanOutcome.IdentifyFailed(
                barcode,
                describeFailure(response.code(), error),
                retake = error?.retake ?: false,
            )
        }
    } catch (e: SocketTimeoutException) {
        ScanOutcome.IdentifyFailed(barcode, "The server is taking too long. Please try again.", retake = false)
    } catch (e: IOException) {
        ScanOutcome.Error("No connection: check your internet and try again.")
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

    /** Asks the server about a product we hold. The answer is grounded in our own
     * data (score, ingredients, NAFDAC and authenticity status, community reports,
     * the user's health goals) and says whether live web research was used. */
    suspend fun ask(barcode: String, question: String, history: List<AskTurn>): Result<AskResponse> = try {
        val response = api.askAboutProduct(barcode, AskRequest(question, history))
        if (response.isSuccessful) {
            Result.success(requireNotNull(response.body()))
        } else {
            Result.failure(IllegalStateException(describeFailure(response)))
        }
    } catch (e: SocketTimeoutException) {
        Result.failure(IllegalStateException("The assistant is taking too long to answer. Please try again."))
    } catch (e: IOException) {
        Result.failure(IllegalStateException("No connection: check your internet and try again."))
    }

    /** One turn of the assistant conversation. Failures are [ChatException]s carrying the
     * server's reason and, for emergency-sounding questions, the safety notice. */
    suspend fun chat(threadId: Int?, message: String, photos: List<File>): Result<ChatReply> = try {
        fun text(value: String) = value.toRequestBody("text/plain".toMediaType())
        val parts = photos.map {
            MultipartBody.Part.createFormData("images", it.name, it.asRequestBody("image/jpeg".toMediaType()))
        }
        val response = api.assistantChat(text(message), threadId?.let { text(it.toString()) }, parts)
        if (response.isSuccessful) {
            Result.success(requireNotNull(response.body()))
        } else {
            val error = parseServerError(response) // read once: the body can't be re-read
            Result.failure(ChatException(describeFailure(response.code(), error), error?.notice))
        }
    } catch (e: SocketTimeoutException) {
        Result.failure(ChatException("The assistant is taking too long to answer. Please try again.", null))
    } catch (e: IOException) {
        Result.failure(ChatException("No connection: check your internet and try again.", null))
    }

    suspend fun chatThreads(): Result<List<ChatThreadSummary>> = runCatching {
        val response = api.assistantThreads()
        if (!response.isSuccessful) error(describeFailure(response))
        requireNotNull(response.body())
    }

    suspend fun chatThread(id: Int): Result<ChatThreadDetail> = runCatching {
        val response = api.assistantThread(id)
        if (!response.isSuccessful) error(describeFailure(response))
        requireNotNull(response.body())
    }

    suspend fun deleteChatThread(id: Int): Result<Unit> = runCatching {
        val response = api.deleteAssistantThread(id)
        if (!response.isSuccessful) error(describeFailure(response))
    }

    suspend fun deleteAllChats(): Result<Unit> = runCatching {
        val response = api.deleteAllAssistantThreads()
        if (!response.isSuccessful) error(describeFailure(response))
    }

    suspend fun rateAnswer(messageId: Int, value: Int, note: String = ""): Result<Unit> = runCatching {
        val response = api.assistantFeedback(messageId, FeedbackRequest(value, note))
        if (!response.isSuccessful) error(describeFailure(response))
    }

    suspend fun assistantSettings(): Result<AssistantSettings> = runCatching {
        val response = api.assistantSettings()
        if (!response.isSuccessful) error(describeFailure(response))
        requireNotNull(response.body())
    }

    suspend fun saveAssistantSettings(settings: AssistantSettings): Result<AssistantSettings> = runCatching {
        val response = api.updateAssistantSettings(settings)
        if (!response.isSuccessful) error(describeFailure(response))
        requireNotNull(response.body())
    }

    /** Cross-checks the product against other sources (country-aware) and returns its updated record. */
    suspend fun researchProduct(barcode: String): Result<ScanResponse> = runCatching {
        val response = api.researchProduct(barcode)
        if (!response.isSuccessful) error(describeFailure(response))
        requireNotNull(response.body())
    }

    /** Tells us a value is wrong. It's a vote: applied only once enough credible people agree. */
    suspend fun submitCorrection(barcode: String, field: String, value: String, reason: String): Result<CorrectionResponse> = runCatching {
        val response = api.submitCorrection(barcode, CorrectionRequest(field, value, reason))
        if (!response.isSuccessful) error(describeFailure(response))
        requireNotNull(response.body())
    }

    suspend fun searchProducts(query: String): Result<SearchResponse> = runCatching {
        val response = api.searchProducts(query)
        if (!response.isSuccessful) error(describeFailure(response))
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

    /** Removes one scan from the user's history and the copy kept on this phone. Only their
     * record goes: the product and what we learned about it stay in the NutriScan data set. */
    suspend fun deleteScan(item: HistoryItem): Result<Unit> = runCatching {
        val response = api.deleteScan(item.id)
        if (!response.isSuccessful && response.code() != 404) error(friendlyErrorMessage(response.code()))
        cachedScanDao.deleteByBarcode(item.product.barcode)
    }

    suspend fun clearHistory(): Result<Unit> = runCatching {
        val response = api.clearHistory()
        if (!response.isSuccessful) error(friendlyErrorMessage(response.code()))
        cachedScanDao.deleteAll()
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
