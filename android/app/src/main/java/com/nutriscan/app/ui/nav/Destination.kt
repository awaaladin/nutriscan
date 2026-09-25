package com.nutriscan.app.ui.nav

sealed class Destination(val route: String) {
    data object Onboarding : Destination("onboarding")
    data object Login : Destination("login")
    data object Home : Destination("home")
    data object Scanner : Destination("scanner")

    data object ProductDetail : Destination("product/{barcode}") {
        fun build(barcode: String) = "product/$barcode"
    }

    data object HealthAnalysis : Destination("analysis/{barcode}") {
        fun build(barcode: String) = "analysis/$barcode"
    }

    data object SubmitProduct : Destination("submit/{barcode}") {
        fun build(barcode: String) = "submit/$barcode"
    }

    data object ProInsights : Destination("pro-insights")
    data object History : Destination("history")
    data object Profile : Destination("profile")
    data object Subscription : Destination("subscription")
}
