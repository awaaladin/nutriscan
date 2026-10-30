from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from django.conf import settings
from django.conf.urls.static import static

from apps.assistant.views import (
    AssistantSettingsView,
    ChatView,
    FeedbackView,
    ThreadDetailView,
    ThreadListView,
)
from apps.community.views import AlertsView, ProductDisputeView, ProductReportsView, ReportFlagView
from apps.products.complete_view import CompleteProductView
from apps.research.views import CorrectionView, ResearchView, SearchView
from apps.products.identify_view import IdentifyProductView
from apps.products.qa_view import ProductAskView
from apps.products.views import (
    AnalyzeView,
    ProductDetailView,
    ProductSubmissionView,
    ScanView,
)
from apps.health.views import HealthLogDetailView, HealthLogListView, HealthSummaryView, HealthToolView
from apps.scans.views import HistoryDetailView, HistoryListView
from apps.subscriptions.views import (
    CreditsView,
    PaystackCheckoutView,
    PaystackPlansView,
    PaystackReturnView,
    PaystackVerifyView,
    PaystackWebhookView,
    ProInsightsView,
    VerifySubscriptionView,
)
from apps.users.views import (
    DeleteAccountView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PreferencesView,
    RegisterView,
    forgot_password_page,
    reset_password_page,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/login/", TokenObtainPairView.as_view(), name="login"),
    path("api/auth/password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("api/auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("reset-password/<uid>/<token>/", reset_password_page, name="reset-password-page"),
    path("forgot-password/", forgot_password_page, name="forgot-password-page"),
    path("api/auth/login/refresh/", TokenRefreshView.as_view(), name="login-refresh"),
    path("api/scan/", ScanView.as_view(), name="scan"),
    path("api/products/submit/", ProductSubmissionView.as_view(), name="product-submit"),
    path("api/products/identify/", IdentifyProductView.as_view(), name="product-identify"),
    path("api/products/search/", SearchView.as_view(), name="product-search"),
    path("api/products/<str:barcode>/", ProductDetailView.as_view(), name="product-detail"),
    path("api/products/<str:barcode>/reports/", ProductReportsView.as_view(), name="product-reports"),
    path("api/products/<str:barcode>/complete/", CompleteProductView.as_view(), name="product-complete"),
    path("api/products/<str:barcode>/research/", ResearchView.as_view(), name="product-research"),
    path("api/products/<str:barcode>/corrections/", CorrectionView.as_view(), name="product-corrections"),
    path("api/products/<str:barcode>/ask/", ProductAskView.as_view(), name="product-ask"),
    path("api/products/<str:barcode>/dispute/", ProductDisputeView.as_view(), name="product-dispute"),
    path("api/alerts/", AlertsView.as_view(), name="alerts"),
    path("api/assistant/chat/", ChatView.as_view(), name="assistant-chat"),
    path("api/assistant/threads/", ThreadListView.as_view(), name="assistant-threads"),
    path("api/assistant/threads/<int:thread_id>/", ThreadDetailView.as_view(), name="assistant-thread"),
    path("api/assistant/messages/<int:message_id>/feedback/", FeedbackView.as_view(), name="assistant-feedback"),
    path("api/assistant/settings/", AssistantSettingsView.as_view(), name="assistant-settings"),
    path("api/reports/<int:report_id>/flag/", ReportFlagView.as_view(), name="report-flag"),
    path("api/analyze/", AnalyzeView.as_view(), name="analyze"),
    path("api/history/", HistoryListView.as_view(), name="history"),
    path("api/history/<int:pk>/", HistoryDetailView.as_view(), name="history-detail"),
    path("api/user/preferences/", PreferencesView.as_view(), name="preferences"),
    path("api/user/account/", DeleteAccountView.as_view(), name="delete-account"),
    path("api/subscription/verify/", VerifySubscriptionView.as_view(), name="subscription-verify"),
    path("api/credits/", CreditsView.as_view(), name="credits"),
    path("api/subscription/paystack/plans/", PaystackPlansView.as_view(), name="paystack-plans"),
    path("api/subscription/paystack/checkout/", PaystackCheckoutView.as_view(), name="paystack-checkout"),
    path("api/subscription/paystack/verify/<str:reference>/", PaystackVerifyView.as_view(), name="paystack-verify"),
    path("api/subscription/paystack/return/", PaystackReturnView.as_view(), name="paystack-return"),
    path("api/subscription/paystack/webhook/", PaystackWebhookView.as_view(), name="paystack-webhook"),
    path("api/health/logs/", HealthLogListView.as_view(), name="health-logs"),
    path("api/health/logs/<int:log_id>/", HealthLogDetailView.as_view(), name="health-log-detail"),
    path("api/health/summary/", HealthSummaryView.as_view(), name="health-summary"),
    path("api/health/<str:tool>/", HealthToolView.as_view(), name="health-tool"),
    path("api/pro/insights/", ProInsightsView.as_view(), name="pro-insights"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
