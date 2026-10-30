import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-secret-key-change-in-production"
    else:
        raise RuntimeError("DJANGO_SECRET_KEY environment variable must be set when DEBUG is False")

# No "*" fallback outside DEBUG -- an unset DJANGO_ALLOWED_HOSTS in production
# should fail closed (reject every Host header) rather than accept any host.
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*" if DEBUG else "").split(",")

# Vercel terminates TLS at its edge and forwards plain HTTP, with the
# original scheme in X-Forwarded-Proto -- without this, request.is_secure()
# is always False behind it and the settings below would redirect-loop.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "apps.users",
    "apps.products",
    "apps.scans",
    "apps.subscriptions",
    "apps.community",
    "apps.assistant",
    "apps.research",
    "apps.health",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if os.environ.get("USE_SQLITE") == "1":
    # Convenience toggle for local dev/tests without a running Postgres instance.
    # Takes priority over DATABASE_URL so a stray .env entry can't make local
    # test runs hit a live hosted database.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
elif os.environ.get("DATABASE_URL"):
    # Hosted Postgres (e.g. Neon) for deployed environments.
    DATABASES = {
        "default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=600, ssl_require=True)
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "nutriscan"),
            "USER": os.environ.get("DB_USER", "nutriscan"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "nutriscan"),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }

AUTH_USER_MODEL = "users.User"

if "test" in sys.argv:
    # PBKDF2 makes every create_user() in test setup take seconds on slow
    # machines; a fast hasher is safe because test passwords are throwaway.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    # Each "ask about this product" question costs an AI call.
    "DEFAULT_THROTTLE_RATES": {"ask": "40/hour", "chat": "60/hour", "research": "30/hour", "corrections": "30/hour", "password-reset": "10/hour"},
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    # Each silent refresh issues a new 30-day refresh token too, so a user
    # who opens the app at least once a month never sees a login prompt
    # again -- the same "stay signed in" behavior as Facebook/Instagram.
    "ROTATE_REFRESH_TOKENS": True,
}

CORS_ALLOW_ALL_ORIGINS = DEBUG

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Report photos. Local disk by default (fine for dev/tests), but Vercel's
# filesystem is ephemeral, so production uses a Vercel Blob store
# (BLOB_READ_WRITE_TOKEN) or, as an alternative, sets CLOUDINARY_URL
# (cloudinary://<key>:<secret>@<cloud_name>) to store evidence photos in
# Cloudinary instead. cloudinary_storage must precede staticfiles in
# INSTALLED_APPS, hence the insert below.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

if os.environ.get("BLOB_READ_WRITE_TOKEN"):
    # Vercel Blob: the token is injected automatically once a Blob store is
    # connected to the Vercel project (see apps.community.blob_storage).
    STORAGES = {
        "default": {"BACKEND": "apps.community.blob_storage.VercelBlobStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
elif os.environ.get("CLOUDINARY_URL"):
    INSTALLED_APPS.insert(INSTALLED_APPS.index("django.contrib.staticfiles"), "cloudinary_storage")
    INSTALLED_APPS.append("cloudinary")
    STORAGES = {
        "default": {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

OPEN_FOOD_FACTS_TIMEOUT = 5

# AI models, tried in order when one is out of daily quota or retired (free-tier
# quotas are per model). Comma-separated override: GEMINI_MODELS="a,b,c". Leave
# unset for the defaults in apps.integrations.vision_identify.DEFAULT_MODELS.
GEMINI_MODELS = [m.strip() for m in os.environ.get("GEMINI_MODELS", "").split(",") if m.strip()]
GEMINI_CHAT_MODELS = [m.strip() for m in os.environ.get("GEMINI_CHAT_MODELS", "").split(",") if m.strip()]

# Google Play subscriptions (see apps.subscriptions.play_client). Product IDs
# must match the subscriptions created in Play Console. With no service
# account configured, purchase verification fails closed -- Pro is never
# granted without Google confirming the purchase.
GOOGLE_PLAY_PACKAGE_NAME = os.environ.get("GOOGLE_PLAY_PACKAGE_NAME", "com.nutriscan.app")
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "")
PLAY_PRODUCT_PLANS = {
    "nutriscan_pro_monthly": "monthly",
    "nutriscan_pro_yearly": "yearly",
}

# Paystack: prepaid Pro bought on the web (see apps.subscriptions.paystack). The account is
# shared with other apps; NutriScan's references start with NUTRISCAN-. Without a key the
# checkout endpoint returns 503 and grants nothing. PAYSTACK_API is accepted as an alias: the
# shared key is stored under that name in the local .env (Choropia reads it the same way).
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "") or os.environ.get("PAYSTACK_API", "")
PAYSTACK_BASE_URL = os.environ.get("PAYSTACK_BASE_URL", "https://api.paystack.co")
# This API's public URL: Paystack sends the payer back to /api/subscription/paystack/return/.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://backend-flame-theta-28.vercel.app")

# --- Email --------------------------------------------------------------------------------
# Gmail SMTP until a domain is verified with a provider such as Resend (then only these settings change).
# Without a password (local development) emails are printed to the console instead.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "465"))
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "true").lower() in ("1", "true", "yes")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "false").lower() in ("1", "true", "yes") and not EMAIL_USE_SSL
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = 8  # Vercel stops a function at 10 seconds
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST_PASSWORD else "django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = os.environ.get("EMAIL_FROM") or os.environ.get("DEFAULT_FROM_EMAIL") or "NutriScan <no-reply@nutriscan.local>"
SERVER_EMAIL = DEFAULT_FROM_EMAIL
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL") or EMAIL_HOST_USER or "support@nutriscan.local"
# How long one payment lasts. A year is charged as YEARLY_MONTHS_CHARGED months.
PAYSTACK_PLAN_DAYS = {"monthly": 30, "yearly": 365}
YEARLY_MONTHS_CHARGED = 10

# --- Plans and AI credits (see apps.subscriptions.credits) ------------------
# One credit is budgeted at about N5 of AI cost (a plain chat answer really costs about N2 on
# Gemini Flash-Lite, a web-searched answer about N48), so a member who spends every credit on
# the most expensive actions still leaves the margin worked out in docs/pricing.md.
PRO_TIERS = {
    "pro": {"label": "Pro", "monthly_ngn": 3000, "monthly_credits": 250},
    "plus": {"label": "Pro Plus", "monthly_ngn": 5000, "monthly_credits": 500},
    "care": {"label": "Pro Care", "monthly_ngn": 7000, "monthly_credits": 750},
}
FREE_MONTHLY_CREDITS = 25
CREDIT_TOPUP = {"credits": 100, "price_ngn": 800}
AI_CREDIT_COSTS = {
    "chat": 1,
    "chat_photos": 2,
    "product_question": 1,
    "research": 10,  # ~2 web searches at $0.014 each (~N48): 20x a plain answer
    "meal_plan": 3,
    "progress_report": 3,
    "doctor_summary": 3,
    "identify": 0,  # adding a missing product helps everyone: metered for cost, never charged
}
# Fair use: at most this many credits in any rolling hour, then an honest cooldown.
AI_CREDITS_PER_HOUR = 40

# For the owner's cost report only (manage.py ai_cost_report): Google's paid-tier prices in
# USD per million tokens, matched on the model name, and the naira rate to convert at.
GEMINI_PRICES_USD_PER_MILLION = {"flash-lite": (0.30, 2.50), "flash": (1.50, 7.50), "pro": (4.00, 20.00)}
GEMINI_SEARCH_USD_PER_QUERY = 0.014
USD_NGN_RATE = float(os.environ.get("USD_NGN_RATE", "1550"))
