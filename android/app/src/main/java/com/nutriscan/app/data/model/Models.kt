package com.nutriscan.app.data.model

/** How far a product's data can be trusted, and exactly why. [level] is verified, corroborated,
 * sourced or unverified. Computed server-side from the evidence we hold. */
data class DataTrust(
    val level: String,
    val headline: String,
    val evidence: List<String> = emptyList(),
    val warnings: List<String> = emptyList(),
    val sources: List<TrustSource> = emptyList(),
    val researched_at: String? = null,
)

data class TrustSource(val type: String = "", val label: String = "", val url: String = "")

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
    val product_type: String? = null,
    val is_estimated: Boolean = false,
    val nafdac_number: String? = null,
    val nafdac_verified: Boolean = false,
    val manufacturer_verified: Boolean = false,
    // Null on responses from older backends.
    val integrity: Integrity? = null,
    val data_trust: DataTrust? = null,
)

/** What our evidence says about a product. [tier] is one of verified,
 * unverified, suspicious, disputed or reported_fake; [reasons] are plain-language
 * lines the UI shows verbatim. There is deliberately no percentage -- nothing
 * can prove a single pack is genuine, so we show evidence instead. */
data class Integrity(
    val tier: String,
    val headline: String,
    val reasons: List<String> = emptyList(),
    val confidence: String = "low",
    val real_votes: Int = 0,
    val fake_votes: Int = 0,
    val checksum_valid: Boolean = true,
    val nafdac_verified: Boolean = false,
    val manufacturer_verified: Boolean = false,
)

data class ReportPhoto(val id: Int, val image: String)

data class ProductReport(
    val id: Int,
    val username: String,
    val verdict: String,
    val comment: String = "",
    val where_bought: String = "",
    val batch_number: String = "",
    val nafdac_number: String = "",
    val photos: List<ReportPhoto> = emptyList(),
    val created_at: String = "",
)

data class ReportsResponse(val integrity: Integrity, val reports: List<ProductReport>)

data class SubmitReportResponse(val report: ProductReport, val integrity: Integrity)

/** What a product means for THIS user (diabetes, blood pressure, weight goal, allergies they noted).
 * [verdict] is Suitable, Caution, Avoid or Unknown; null when they've told us nothing that changes
 * how a product should be judged for them. */
data class ForYou(
    val verdict: String,
    val headline: String,
    val reasons: List<String> = emptyList(),
    val conditions: List<String> = emptyList(),
)

data class ScanResponse(
    val product: Product,
    // Null for a non-food item (see product_type) -- WHO scoring doesn't apply to those.
    val scan_id: Int? = null,
    val score: Int? = null,
    val label: String? = null,
    val diabetic_risk: String? = null,
    val flags: List<String> = emptyList(),
    val insufficient_data: Boolean = false,
    // Which nutrients we have no value for, e.g. ["sugar", "sodium"].
    val missing_nutrients: List<String> = emptyList(),
    // Plain-language reasons behind the label and the diabetic risk.
    val reasons: List<String> = emptyList(),
    val diabetic_reasons: List<String> = emptyList(),
    // True when judged as a drink (per 100 ml, stricter sugar limits).
    val beverage: Boolean = false,
    val for_you: ForYou? = null,
    // Present on the response to the research call: what the cross-check did.
    val research: ResearchInfo? = null,
    val explanation: String? = null,
    val product_type: String? = null,
    val detail: String? = null,
    val is_estimated: Boolean = false,
    // "database" (already on file, no AI used), "twin" (matched by NAFDAC number) or "ai" (just researched).
    val source: String? = null,
)

data class ScanRequest(val barcode: String)

data class HistoryItem(
    val id: Int,
    val product: Product,
    // Null when the label is "Incomplete": there is no honest number to show.
    val score: Int?,
    val label: String,
    val diabetic_risk: String,
    val flags: List<String>,
    val insufficient_data: Boolean = false,
    val missing_nutrients: List<String> = emptyList(),
    val reasons: List<String> = emptyList(),
    val diabetic_reasons: List<String> = emptyList(),
    val beverage: Boolean = false,
    val for_you: ForYou? = null,
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

/** One row of the Alerts list: a product with credible fake reports. */
data class AlertItem(
    val barcode: String,
    val name: String,
    val brand: String? = null,
    val tier: String,
    val headline: String,
    val fake_votes: Int,
    val places: List<String> = emptyList(),
    val latest_report_at: String = "",
)

data class DisputeRequest(
    val company_name: String,
    val contact: String,
    val message: String,
    val nafdac_number: String = "",
)

/** One turn of the "ask about this product" conversation; [role] is "user" or "assistant". */
data class AskTurn(val role: String, val text: String)

data class AskRequest(val question: String, val history: List<AskTurn> = emptyList())

data class AskSource(val title: String, val url: String)

/** [web_research] is false when the answer came from our own data and the AI's
 * knowledge only (live web search wasn't available). */
data class AskResponse(
    val answer: String,
    val sources: List<AskSource> = emptyList(),
    val web_research: Boolean = false,
)

// ---- Assistant chat -----------------------------------------------------------------------

/** One message of a saved conversation. Photos a user attached are not stored server-side,
 * only [image_count]. [feedback] is 1 (helpful), -1 (not helpful) or null. */
data class ChatMessageDto(
    val id: Int,
    val role: String,
    val text: String,
    val image_count: Int = 0,
    val web_research: Boolean = false,
    val sources: List<AskSource> = emptyList(),
    val feedback: Int? = null,
    val created_at: String = "",
)

/** [notice] is a fixed safety message (e.g. "call 112") sent when the question sounds like an emergency. */
data class ChatReply(
    val thread_id: Int,
    val title: String,
    val message: ChatMessageDto,
    val notice: String? = null,
)

data class ChatThreadSummary(val id: Int, val title: String, val updated_at: String = "")

data class ChatThreadDetail(val id: Int, val title: String, val messages: List<ChatMessageDto>)

/** What the assistant knows about the user, and whether their (anonymised) chats may help train NutriScan. */
data class AssistantSettings(
    val health_notes: String = "",
    val allow_training_use: Boolean = false,
)

data class FeedbackRequest(val value: Int, val note: String = "")

/** What a research run did: [applied] are the fields filled in from other sources. */
data class ResearchInfo(
    val ran: Boolean = false,
    val applied: List<String> = emptyList(),
    val conflicts: List<String> = emptyList(),
    val skipped: List<String> = emptyList(),
)

data class CorrectionRequest(val field: String, val value: String, val reason: String = "")

data class CorrectionResponse(val applied: Boolean = false, val detail: String = "")

data class TrustBrief(val level: String = "unverified", val headline: String = "")

/** One product found by searching our own data set. */
data class SearchResult(
    val barcode: String,
    val name: String,
    val brand: String? = null,
    val nafdac_number: String? = null,
    val product_type: String? = null,
    val trust: TrustBrief = TrustBrief(),
    val label: String? = null,
    val score: Int? = null,
    val diabetic_risk: String? = null,
)

data class SearchResponse(val query: String = "", val results: List<SearchResult> = emptyList())
