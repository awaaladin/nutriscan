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
    "DEFAULT_THROTTLE_RATES": {"ask": "40/hour"},
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
