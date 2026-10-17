package com.nutriscan.app.data.remote

import com.nutriscan.app.data.model.AlertItem
import com.nutriscan.app.data.model.AskRequest
import com.nutriscan.app.data.model.AskResponse
import com.nutriscan.app.data.model.DisputeRequest
import com.nutriscan.app.data.model.HistoryItem
import com.nutriscan.app.data.model.LoginRequest
import com.nutriscan.app.data.model.PreferencesUpdateRequest
import com.nutriscan.app.data.model.ProInsights
import com.nutriscan.app.data.model.Product
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
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path

interface ApiService {
    @POST("api/auth/register/")
    suspend fun register(@Body request: RegisterRequest): Response<RegisterResponse>

    @POST("api/auth/login/")
    suspend fun login(@Body request: LoginRequest): Response<TokenPair>

    @POST("api/scan/")
    suspend fun scan(@Body request: ScanRequest): Response<ScanResponse>

    @GET("api/products/{barcode}/")
    suspend fun getProduct(@Path("barcode") barcode: String): Response<Product>

    @POST("api/products/submit/")
    suspend fun submitProduct(@Body request: ProductSubmissionRequest): Response<Unit>

    @Multipart
    @POST("api/products/identify/")
    suspend fun identifyProduct(
        // Null when no barcode was read at all -- the server then reads it off the photos.
        // Retrofit omits a null @Part entirely rather than sending an empty value.
        @Part("barcode") barcode: RequestBody?,
        // Optional NAFDAC number typed by the user: if we already have it, no AI call is made.
        @Part("nafdac_number") nafdacNumber: RequestBody?,
        // One part per side of the product (the app requires at least 3).
        @Part images: List<MultipartBody.Part>,
    ): Response<ScanResponse>

    @GET("api/products/{barcode}/reports/")
    suspend fun getReports(@Path("barcode") barcode: String): Response<ReportsResponse>

    @Multipart
    @POST("api/products/{barcode}/reports/")
    suspend fun submitReport(
        @Path("barcode") barcode: String,
        @Part("verdict") verdict: RequestBody,
        @Part("comment") comment: RequestBody,
        @Part("where_bought") whereBought: RequestBody,
        @Part("batch_number") batchNumber: RequestBody,
        @Part("nafdac_number") nafdacNumber: RequestBody,
        @Part photos: List<MultipartBody.Part>,
    ): Response<SubmitReportResponse>

    @POST("api/products/{barcode}/ask/")
    suspend fun askAboutProduct(@Path("barcode") barcode: String, @Body request: AskRequest): Response<AskResponse>

    @GET("api/alerts/")
    suspend fun getAlerts(): Response<List<AlertItem>>

    @POST("api/products/{barcode}/dispute/")
    suspend fun submitDispute(@Path("barcode") barcode: String, @Body request: DisputeRequest): Response<Unit>

    @POST("api/reports/{id}/flag/")
    suspend fun flagReport(@Path("id") reportId: Int, @Body body: Map<String, String>): Response<Unit>

    @GET("api/history/")
    suspend fun getHistory(): Response<List<HistoryItem>>

    @GET("api/user/preferences/")
    suspend fun getPreferences(): Response<UserPreferences>

    @PATCH("api/user/preferences/")
    suspend fun updatePreferences(@Body request: PreferencesUpdateRequest): Response<UserPreferences>

    @POST("api/subscription/verify/")
    suspend fun verifySubscription(@Body request: VerifyPurchaseRequest): Response<SubscriptionStatus>

    @GET("api/pro/insights/")
    suspend fun getProInsights(): Response<ProInsights>
}
