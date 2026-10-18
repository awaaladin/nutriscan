# NutriScan

Scans barcodes of packaged food, returns nutrition data, a WHO-threshold health
score, and a diabetic risk tier. Nigeria-first product coverage via Open Food
Facts + community submissions.

## Repo layout

```
backend/    Django + DRF API, PostgreSQL, scoring engine
android/    Kotlin + Jetpack Compose native Android app
download/   Beta download page (nutriscan-download.vercel.app); run publish.sh
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

The suite covers the scoring engine (pure logic, no DB), the scan/analyze/submit
endpoints, auth + preferences, history, the subscription verify/pro-insights
flow, and the integrity score + community reports. It is slow on Windows
(minutes) because of password hashing in test setup.

### Counterfeit protection: evidence tiers and community reports

Nothing can prove a single pack is genuine (fakers copy real barcodes and even
real NAFDAC numbers), so every product carries an `integrity` object with an
evidence **tier** and plain-language reasons, not a percentage. Tiers
(`apps/community/integrity.py`, highest priority first): `reported_fake`,
`disputed`, `verified`, `suspicious`, `unverified`. Credible user reports can
override a registry match.

- **NAFDAC:** a number is captured from reports or read off the pack photo by
  the vision step, and format-checked. NAFDAC has no official API (only the
  Greenbook search site), so an admin confirms it there and uses the
  "Mark NAFDAC number verified" action on Product in Django admin. Only then
  does it count. `manufacturer_verified` is set the same way.
- **Reports:** one real/fake report per user per product, up to 4 photos,
  where bought, batch number. Reports are weighted: photos and a batch number
  add weight, accounts under 2 days count 0.25x and under 14 days 0.6x, and
  users an admin marks `is_verified_reviewer` count 3x, so mass-created
  accounts can't swing a product.
- **Alerts:** `GET /api/alerts/` is a ranked list of products at
  `reported_fake`/`disputed` in the last 60 days with the places they were
  bought. There is deliberately no social feed.
- **Moderation:** users flag abusive reports; admins hide reports (excluded from
  scoring) and review manufacturer disputes (`POST /api/products/<barcode>/dispute/`)
  in Django admin.
- Products identified by AI from a photo are saved, so later scans of that
  barcode never call the AI again.

Report photos need persistent storage in production. A Vercel Blob store
(`nutriscan-report-photos`, public) is connected to the Vercel `backend`
project, which injects `BLOB_READ_WRITE_TOKEN`; settings then switch to
`apps/community/blob_storage.py`. `CLOUDINARY_URL` is supported as an
alternative. With neither set, photos go to local disk, which Vercel wipes
between deployments.

### Subscriptions (Google Play)

Pro is granted only after the backend confirms a purchase token with the Google
Play Developer API (`apps/subscriptions/play_client.py`); the client never
decides plan or expiry. Without `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` the verify
endpoint returns 503 and grants nothing. Set up:

1. Create subscriptions `nutriscan_pro_monthly` and `nutriscan_pro_yearly` in
   Play Console.
2. Create a Google Cloud service account, enable the Google Play Android
   Developer API, and invite its email in Play Console (Users and permissions)
   with "View financial data" and "Manage orders and subscriptions".
3. Set `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` (the key file's contents) and, if the
   package differs, `GOOGLE_PLAY_PACKAGE_NAME` on the host.
4. Billing only works for builds installed from Play (use an internal testing
   track), not plain debug installs.

Renewals are picked up by re-checking with Google once a stored expiry passes;
there is no Pub/Sub webhook yet.

### AI features and Google AI limits

Photo research, "ask about this product" and the one-sentence health explanations
all use the Gemini API through `apps/integrations/vision_identify.py`:

- Models are tried in order (`GEMINI_MODELS` for photos, `GEMINI_CHAT_MODELS` for
  chat/explanations): a model that is out of daily quota (429) or retired (404)
  hands over to the next, transient 429/5xx errors are retried, and every failure
  surfaces as a specific reason to the app instead of a generic error.
- The free tier meters requests per model per day and does not allow web search
  ("grounding"), so questions are then answered from NutriScan's own data and
  say so. Enabling billing on the Google AI Studio project removes both limits.
- Data first: a barcode (any zero-padded form) or NAFDAC number already on file is
  answered from the database with no AI call; products researched from photos are
  saved so later scans are instant.

### The assistant ("Ask NutriScan")

A full-page chat (`apps/assistant`, Android `ChatScreen`) specialised in nutrition,
medicines and spotting counterfeit products, personal to the user:

- **Personal:** answers use the user's profile, optional health notes (allergies,
  conditions, medicines) and recent scans with their *current* verdicts, plus any
  products from our own database the message mentions (by barcode, NAFDAC number or
  name). Our data comes first; the AI is told our scores and authenticity tiers are
  the source of truth.
- **Photos:** up to 3 per message (food pack, nutrition table, medicine box...). They
  are read for that one answer and **not stored** (only a count is kept). It never
  identifies a pill from its looks.
- **Safety:** no diagnosis or personal doses (it points to a pharmacist), and
  emergency wording ("overdose", "chest pain"...) gets a fixed "call 112" notice that
  doesn't depend on the AI being reachable.
- **Privacy:** chats belong to one account and are not registered in Django admin.
  Users can delete one chat or all of them.
- **Learning from it (not a model we train yet):** thumbs up/down on every answer, and
  an opt-in (off by default, withdrawable) to include a user's chats in a training
  set. `python manage.py export_training_data --out ./training` writes only consented
  and rated conversations, anonymised (no ids; emails, phone numbers and long numbers
  scrubbed) as `good.jsonl` and `review.jsonl`. Review the files before using them:
  scrubbing is best-effort. Actually fine-tuning a model needs thousands of reviewed
  examples; this builds that dataset.

### Trusted data set and research (apps/research)

Every product carries a **data trust** level computed from stored evidence, never
asserted: `verified` (NAFDAC confirmed), `corroborated` (two independent sources
agree), `sourced` (one cited source) or `unverified`.

- `research_product` cross-checks a product against Open Food Facts (name + brand +
  country aware; GS1 prefix 615 = Nigeria). Blanks are filled only when a source agrees
  on at least two fields and conflicts on none; existing values are never overwritten;
  conflicts become open corrections for review. AI web research is used only when live
  web search ran and cited pages (needs Google AI billing); memory-only answers are never evidence.
- Users report corrections (`POST /api/products/<barcode>/corrections/`). They are votes,
  weighted by account age and reviewer status, and NEVER enough alone (votes can be manipulated): applied only when credible users agree AND an independent source backs the same value, or an admin accepts.
- `GET /api/products/search/?q=` searches the data set by name, brand, barcode or NAFDAC.
- The assistant retrieves **approved** `KnowledgeEntry` rows ("reviewed answers"). Build
  candidates with `manage.py build_knowledge_base` (consented, thumbs-up chats only), approve
  in admin, export with `export_knowledge_base`, and check `dataset_readiness` to see when
  enough reviewed data exists (1000 Q&A, 500 trusted products) to fine-tune a model.
- Batch research: `manage.py research_products`.

### Branding

The logo is the loading-screen mark: a gold disc with the QR-scanner icon on deep green.
`branding/logo.svg` is the source; `branding/png/` and `favicon.ico` are renders of it, and
`res/drawable/ic_logo.xml` is the Android vector (launcher icon, splash, app bar). All of them,
plus the copies in `download/` (page logo, favicons, `og-image.png`), are generated by one
script so they can never drift apart: `python make_logo.py` (kept in `branding/make_logo.py`).

### How scoring works (apps/scoring)

The headline health score is universal (so products are comparable); a separate
**"for you"** verdict personalises it. Both are deterministic rules, never AI output:

- **Score (1-10, Good/Moderate/Avoid):** per-100 g/100 ml WHO-style tiers for sugar,
  saturated fat and sodium. Any single "high" nutrient caps the product at Moderate
  (score at most 6). **Drinks** (detected from the name, or "carbonated water" first)
  use half the sugar limits. A product that would be Good but has missing nutrition
  is **Incomplete** (no number); known-bad verdicts stand because unknowns can only
  make them worse. Every verdict carries plain-language `reasons`.
- **Diabetic risk (Safe/Moderate/Avoid/Unknown):** sugar (stricter for drinks),
  refined-carbohydrate ingredients ("sugar free" claims are not counted), and net
  carbohydrate (minus fibre) which only ever raises to Moderate and is waived for
  high-fibre whole grains and for sugar-alcohol products with low sugar. Sugar and
  carbohydrate both unknown is Unknown, not Safe.
- **For you (Suitable/Caution/Avoid/Unknown):** built from the user's profile - diabetes
  (or that health goal), high blood pressure (sodium), a weight-loss goal (energy
  density, sugar, saturated fat) and **allergies parsed from their health notes**
  ("Allergic to peanuts and milk"; negations like "not allergic to..." are ignored).
  It only ever adds warnings: no allergen found is never described as "safe for your
  allergy", because the ingredient list may be missing or incomplete.
- History and every endpoint use the same helper (`apps/products/scoring_helpers.py`)
  and recompute from the product's current data, so past scans are always corrected.

### What's real vs. stubbed

- **Real**: WHO-threshold scoring engine (`apps/scoring/engine.py`), diabetic
  risk tiering, Open Food Facts integration, community product submissions,
  JWT auth, scan history, LLM explanation caching.
- **Stubbed** (flagged with `TODO` in code):
  - `apps/integrations/llm_explanations.py` returns a deterministic template
    instead of calling a real LLM. Swap `get_explanation_provider()`.

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
- **Real**: the Subscription screen runs a Google Play Billing purchase and
  sends the token to the backend for verification (see Subscriptions above).

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
