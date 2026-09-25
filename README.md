# NutriScan

Scans barcodes of packaged food, returns nutrition data, a WHO-threshold health
score, and a diabetic risk tier. Nigeria-first product coverage via Open Food
Facts + community submissions.

## Repo layout

```
backend/    Django + DRF API, PostgreSQL, scoring engine
android/    Kotlin + Jetpack Compose native Android app
```

## Backend

### Setup

```
cd backend
pip install -r requirements.txt
```

Run against PostgreSQL (production-like):

```
set DB_NAME=nutriscan
set DB_USER=nutriscan
set DB_PASSWORD=nutriscan
set DB_HOST=localhost
python manage.py migrate
python manage.py runserver
```

Or run against SQLite for quick local dev / tests (no Postgres required):

```
set USE_SQLITE=1
python manage.py migrate
python manage.py runserver
```

### Tests

```
set USE_SQLITE=1
python manage.py test
```

All 18 tests pass as of this scaffold, covering: the scoring engine (pure
logic, no DB), the scan/analyze/submit endpoints, auth + preferences, history,
and the subscription verify/pro-insights flow.

### What's real vs. stubbed

- **Real**: WHO-threshold scoring engine (`apps/scoring/engine.py`), diabetic
  risk tiering, Open Food Facts integration, community product submissions,
  JWT auth, scan history, LLM explanation caching.
- **Stubbed** (flagged with `TODO` in code):
  - `apps/integrations/llm_explanations.py` returns a deterministic template
    instead of calling a real LLM. Swap `get_explanation_provider()`.
  - `apps/subscriptions/views.py` `VerifySubscriptionView` trusts the
    client-reported purchase token instead of calling the Google Play
    Developer API. Do not ship this to production as-is.

## Android

Kotlin + Jetpack Compose, minSdk 26, targetSdk 34. Uses CameraX + ML Kit for
barcode scanning, Retrofit for the API, Room for offline scan cache, DataStore
for the JWT session.

### Build

```
cd android
./gradlew assembleDebug
```

The debug build points at `http://10.0.2.2:8000/` (the Android emulator's
alias for the host machine's `localhost`), so run the Django dev server on
your host before testing scan flows from the emulator. For a physical device,
change `API_BASE_URL` in `app/build.gradle.kts` to your machine's LAN IP.

### Screens (11)

Splash/Onboarding, Login/Register, Home Dashboard, Barcode Scanner, Product
Detail, Health Analysis, Submit Missing Product, Pro Insights, History,
Profile & Health Settings, Subscription/Upgrade.

### What's real vs. stubbed

- **Real**: full navigation graph, camera barcode scanning, manual barcode
  entry fallback, Retrofit API client with JWT auth interceptor, Room offline
  cache with fallback when a scan request fails due to no connectivity,
  history filtering, profile preference toggles.
- **Stubbed**: the Subscription screen calls `subscription/verify/` with a
  placeholder purchase token instead of running a real Google Play Billing
  purchase flow. Wire up the Play Billing Library before shipping Pro.

## Before this goes to production

1. Replace the LLM explanation stub with a real provider, keeping the rules
   engine as the sole source of truth for scores (see the module docstring).
2. Replace the subscription verify stub with real Google Play Developer API
   receipt validation, plus Real-Time Developer Notifications for
   renewals/cancellations.
3. Seed the community product table with known Nigerian packaged foods —
   Open Food Facts coverage for Nigeria is thin, which is exactly why the
   submission flow exists.
4. Review `config/settings.py` for production values (`DJANGO_SECRET_KEY`,
   `DEBUG=False`, `ALLOWED_HOSTS`) before deploying.
