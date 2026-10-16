package com.nutriscan.app.data.model

data class Product(
    val id: Int? = null,
    val barcode: String,
    val name: String,
    val brand: String? = null,
    val source: String? = null,
    val calories_kcal: Double? = null,
    val sugar_g: Double? = null,
    val saturated_fat_g: Double? = null,
    val sodium_mg: Double? = null,
    val carbohydrates_g: Double? = null,
    val fiber_g: Double? = null,
    val protein_g: Double? = null,
    val ingredients_text: String? = null,
    val additives: List<String> = emptyList(),
    val image_url: String? = null,
    // Null on responses from older backends.
    val integrity: Integrity? = null,
)

/** How likely our data says a product is genuine (0-100), blending barcode
 * signals with community real/fake votes. [confidence] is low/medium/high by
 * vote count -- a low-confidence percentage is mostly the barcode prior. */
data class Integrity(
    val percent: Int,
    val confidence: String,
    val real_votes: Int,
    val fake_votes: Int,
    val checksum_valid: Boolean,
    val in_independent_db: Boolean,
)

data class ReportPhoto(val id: Int, val image: String)

data class ProductReport(
    val id: Int,
    val username: String,
    val verdict: String,
    val comment: String = "",
    val where_bought: String = "",
    val batch_number: String = "",
    val photos: List<ReportPhoto> = emptyList(),
    val created_at: String = "",
)

data class ReportsResponse(val integrity: Integrity, val reports: List<ProductReport>)

data class SubmitReportResponse(val report: ProductReport, val integrity: Integrity)

data class ScanResponse(
    val product: Product,
    // Null for a non-food item (see product_type) -- WHO scoring doesn't apply to those.
    val scan_id: Int? = null,
    val score: Int? = null,
    val label: String? = null,
    val diabetic_risk: String? = null,
    val flags: List<String> = emptyList(),
    val insufficient_data: Boolean = false,
    val explanation: String? = null,
    val product_type: String? = null,
    val detail: String? = null,
    val is_estimated: Boolean = false,
)

data class ScanRequest(val barcode: String)

data class HistoryItem(
    val id: Int,
    val product: Product,
    val score: Int,
    val label: String,
    val diabetic_risk: String,
    val flags: List<String>,
    val scanned_at: String,
)

data class RegisterRequest(
    val username: String,
    val email: String,
    val password: String,
    val region: String = "NG",
    val primary_goal: String = "general_health",
)

data class LoginRequest(val username: String, val password: String)

data class TokenPair(val access: String, val refresh: String)

data class UserPreferences(
    val id: Int? = null,
    val username: String? = null,
    val email: String? = null,
    val primary_goal: String = "general_health",
    val is_diabetic: Boolean = false,
    val has_hypertension: Boolean = false,
    val region: String = "NG",
    val is_pro: Boolean = false,
)

data class PreferencesUpdateRequest(
    val primary_goal: String? = null,
    val is_diabetic: Boolean? = null,
    val has_hypertension: Boolean? = null,
    val region: String? = null,
)

data class RegisterResponse(
    val user: UserPreferences,
    val access: String,
    val refresh: String,
)

data class ProductSubmissionRequest(
    val barcode: String,
    val name: String,
    val brand: String,
    val nutrition_payload: Map<String, Double?>,
    val ingredients_text: String,
)

/** Only the token and product go to the server -- it asks Google Play what was
 * actually bought, so the client can't claim a plan or expiry itself. */
data class VerifyPurchaseRequest(
    val purchase_token: String,
    val product_id: String,
)

data class SubscriptionStatus(
    val plan: String,
    val status: String,
    val expires_at: String?,
)

data class AvoidProduct(val barcode: String, val name: String)

data class ProInsights(
    val avoid_list: List<AvoidProduct>,
    val patterns: List<String>,
)
