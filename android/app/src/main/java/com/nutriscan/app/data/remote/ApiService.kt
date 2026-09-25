package com.nutriscan.app.data.remote

import com.nutriscan.app.data.model.HistoryItem
import com.nutriscan.app.data.model.LoginRequest
import com.nutriscan.app.data.model.PreferencesUpdateRequest
import com.nutriscan.app.data.model.ProInsights
import com.nutriscan.app.data.model.Product
import com.nutriscan.app.data.model.ProductSubmissionRequest
import com.nutriscan.app.data.model.RegisterRequest
import com.nutriscan.app.data.model.RegisterResponse
import com.nutriscan.app.data.model.ScanRequest
import com.nutriscan.app.data.model.ScanResponse
import com.nutriscan.app.data.model.SubscriptionStatus
import com.nutriscan.app.data.model.TokenPair
import com.nutriscan.app.data.model.UserPreferences
import com.nutriscan.app.data.model.VerifyPurchaseRequest
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
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
