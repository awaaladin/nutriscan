from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.products.views import AnalyzeView, ProductDetailView, ProductSubmissionView, ScanView
from apps.scans.views import HistoryListView
from apps.subscriptions.views import ProInsightsView, VerifySubscriptionView
from apps.users.views import PreferencesView, RegisterView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/login/", TokenObtainPairView.as_view(), name="login"),
    path("api/auth/login/refresh/", TokenRefreshView.as_view(), name="login-refresh"),
    path("api/scan/", ScanView.as_view(), name="scan"),
    path("api/products/submit/", ProductSubmissionView.as_view(), name="product-submit"),
    path("api/products/<str:barcode>/", ProductDetailView.as_view(), name="product-detail"),
    path("api/analyze/", AnalyzeView.as_view(), name="analyze"),
    path("api/history/", HistoryListView.as_view(), name="history"),
    path("api/user/preferences/", PreferencesView.as_view(), name="preferences"),
    path("api/subscription/verify/", VerifySubscriptionView.as_view(), name="subscription-verify"),
    path("api/pro/insights/", ProInsightsView.as_view(), name="pro-insights"),
]
