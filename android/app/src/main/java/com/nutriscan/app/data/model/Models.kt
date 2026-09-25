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
)

data class ScanResponse(
    val scan_id: Int,
    val product: Product,
    val score: Int,
    val label: String,
    val diabetic_risk: String,
    val flags: List<String>,
    val insufficient_data: Boolean,
    val explanation: String,
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

data class VerifyPurchaseRequest(
    val plan: String,
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
