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
    val accept_terms: Boolean = false,
    val health_consent: Boolean = false,
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
    /** "free", "pro", "plus" or "care". */
    val tier: String = "free",
    val bonus_credits: Int = 0,
    val height_cm: Int? = null,
    val target_weight_kg: Double? = null,
    val terms_accepted_at: String? = null,
    val health_consent_at: String? = null,
)

data class PreferencesUpdateRequest(
    val primary_goal: String? = null,
    val is_diabetic: Boolean? = null,
    val has_hypertension: Boolean? = null,
    val region: String? = null,
    val height_cm: Int? = null,
    val target_weight_kg: Double? = null,
    val accept_terms: Boolean? = null,
    val health_consent: Boolean? = null,
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

/** One paid plan, priced by the server. Each tier includes everything below it. */
data class TierInfo(
    val tier: String,
    val label: String,
    val monthly_ngn: Int,
    val yearly_ngn: Int,
    val monthly_credits: Int,
    val features: List<String> = emptyList(),
)

data class TopUp(val credits: Int, val price_ngn: Int)

/** What the user has left. Monthly credits renew on [renews_on]; bought ones never expire. */
data class CreditBalance(
    val tier: String = "free",
    val monthly_allowance: Int = 0,
    val used_this_month: Int = 0,
    val monthly_remaining: Int = 0,
    val bonus_credits: Int = 0,
    val total_remaining: Int = 0,
    val renews_on: String = "",
    val costs: Map<String, Int> = emptyMap(),
)

data class PlansResponse(
    val tiers: List<TierInfo>,
    val free_monthly_credits: Int,
    val topup: TopUp,
    val credit_costs: Map<String, Int> = emptyMap(),
    val balance: CreditBalance,
)

/** A plan period ([kind] "subscription": [tier] + [plan] monthly/yearly) or a credit top-up
 * ([kind] "credits"). [email] is only sent for accounts registered without one. */
data class CheckoutRequest(
    val kind: String = "subscription",
    val tier: String = "pro",
    val plan: String = "monthly",
    val email: String? = null,
)

/** [authorization_url] is Paystack's payment page, opened in the browser rather than the app. */
data class CheckoutResponse(val reference: String, val authorization_url: String)

/** One reading the user logged: weight (kg), blood pressure, or blood glucose (mg/dL). */
data class HealthLog(
    val id: Int? = null,
    val kind: String,
    val value: Double? = null,
    val systolic: Int? = null,
    val diastolic: Int? = null,
    val timing: String = "",
    val note: String = "",
    val measured_at: String? = null,
    /** An urgent warning for a dangerous reading, from the server. */
    val alert: String? = null,
)

data class WeightSummary(
    val count: Int,
    val latest_kg: Double,
    val change_kg: Double,
    val bmi: Double? = null,
    val target_kg: Double? = null,
    val to_target_kg: Double? = null,
)

data class PressureSummary(val count: Int, val latest: String, val avg_7d: String, val in_target_pct: Int, val target: String)

data class GlucoseSummary(
    val count: Int,
    val latest_mg_dl: Double,
    val latest_timing: String = "",
    val avg_fasting_mg_dl: Double? = null,
    val avg_after_meal_mg_dl: Double? = null,
    val in_target_pct: Int,
    val lows: Int,
    val target: String,
)

data class HealthSummary(
    val tier: String = "free",
    val weight: WeightSummary? = null,
    val blood_pressure: PressureSummary? = null,
    val glucose: GlucoseSummary? = null,
    val alerts: List<String> = emptyList(),
    /** Which trackers and AI tools the plan unlocks, by kind/tool name. */
    val unlocked: Map<String, Boolean> = emptyMap(),
    val height_cm: Int? = null,
    val target_weight_kg: Double? = null,
)

data class HealthToolRequest(val note: String = "")

data class HealthToolResponse(val tool: String, val text: String, val credits_left: Int? = null)

data class DeleteAccountRequest(val password: String)

/** Pro is only ever switched on from what Paystack reports to the server, never by the app. */
data class PaymentStatus(val reference: String, val status: String, val is_pro: Boolean)

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

/** [trusted] marks a credible health source (WHO, NIH, NAFDAC, ADA...) in Research mode answers. */
data class AskSource(val title: String, val url: String, val trusted: Boolean = false)

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
    val credits_left: Int? = null,
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
