package com.nutriscan.app.ui.nav

sealed class Destination(val route: String) {
    data object Splash : Destination("splash")
    data object Onboarding : Destination("onboarding")
    data object Login : Destination("login")
    data object Home : Destination("home")
    data object Scanner : Destination("scanner")
    data object Analyzing : Destination("analyzing")

    /** Photographing a product we don't know (or retaking the photos after a
     * failed attempt). "none" stands in for "no barcode was scanned". */
    data object Capture : Destination("capture/{barcode}") {
        fun build(barcode: String?) = "capture/${barcode?.takeIf { it.isNotBlank() } ?: "none"}"
    }

    data object ProductDetail : Destination("product/{barcode}") {
        fun build(barcode: String) = "product/$barcode"
    }

    data object HealthAnalysis : Destination("analysis/{barcode}") {
        fun build(barcode: String) = "analysis/$barcode"
    }

    data object SubmitProduct : Destination("submit/{barcode}") {
        fun build(barcode: String) = "submit/$barcode"
    }

    data object Reports : Destination("reports/{barcode}") {
        fun build(barcode: String) = "reports/$barcode"
    }

    data object SubmitReport : Destination("report/{barcode}") {
        fun build(barcode: String) = "report/$barcode"
    }

    /** Photograph the nutrition table of a product we already hold, to complete it. */
    data object CaptureNutrition : Destination("capture-nutrition/{barcode}") {
        fun build(barcode: String) = "capture-nutrition/$barcode"
    }

    /** Type in a product's missing nutrition values. */
    data object NutritionEntry : Destination("nutrition/{barcode}") {
        fun build(barcode: String) = "nutrition/$barcode"
    }

    data object Ask : Destination("ask/{barcode}") {
        fun build(barcode: String) = "ask/$barcode"
    }

    data object Alerts : Destination("alerts")

    data object Dispute : Destination("dispute/{barcode}") {
        fun build(barcode: String) = "dispute/$barcode"
    }

    data object ProInsights : Destination("pro-insights")
    data object History : Destination("history")
    data object Profile : Destination("profile")
    data object Subscription : Destination("subscription")
    data object Settings : Destination("settings")
    data object Achievements : Destination("achievements")
    data object Insights : Destination("insights")
}
