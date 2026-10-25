# NutriScan pricing and AI costs

How the plan prices, AI credits and margins were worked out. The live numbers come from
`python manage.py ai_cost_report` (run from `backend/`), which uses Gemini's own token count
for every call. Re-check this page against it after the first month.

## Assumptions

- ₦1,550 = $1 (`USD_NGN_RATE` setting; change it when the rate moves).
- Gemini paid tier. Chat runs on Gemini 3.5 Flash-Lite: $0.30 per million tokens in, $2.50 out.
- Google web search (Research mode only): $0.014 per search after 5,000 free searches a month
  shared by all users. A research answer usually runs about 2 searches.
- Paystack local cards: 1.5%, plus ₦100 from ₦2,500 up, capped at ₦2,000.
- Not included: Vercel and Neon hosting, staff, tax.

## What one AI action costs us

Measured on 2026-10-24 with the real prompts (instructions, the user's profile and scans, 6
earlier messages):

| Action | Tokens in / out | Our cost | Credits charged | Budget at ₦5/credit |
|---|---|---|---|---|
| Chat message | ~2,500 / ~300 | ~₦2.30 | 1 | ₦5 |
| Chat with photos | ~5,800 / ~300 | ~₦3.90 | 2 | ₦10 |
| Product question | ~1,500 / ~250 | ~₦1.70 | 1 | ₦5 |
| Research answer (2 searches) | ~3,500 / ~700 | ~₦48 | 10 | ₦50 |
| Meal plan / weekly report / doctor summary | ~3,000 / ~1,500 | ~₦7 | 3 | ₦15 |
| Adding a missing product by photo | varies | ~₦10–20 | 0 (free) | — |

One credit is budgeted at ₦5. Every charged action costs us less than its credit budget, so the
margins below hold even for a member who uses every credit.

If Flash-Lite is unavailable, the app falls back to bigger models that cost about 5 times more.
To protect margins, production sets `GEMINI_CHAT_MODELS` to the Flash-Lite models only.

## Plans

A year costs 10 months' price (2 months free).

| Plan | Price | Credits a month | Includes |
|---|---|---|---|
| Free | ₦0 | 25 | Scanning, health score, diabetic risk tier, AI chat |
| Pro | ₦3,000/mo, ₦30,000/yr | 250 | + Research mode, avoid-list and scan patterns, weight tracker |
| Pro Plus | ₦5,000/mo, ₦50,000/yr | 500 | + blood pressure tracker, 7-day meal plans, weekly AI report |
| Pro Care | ₦7,000/mo, ₦70,000/yr | 750 | + blood sugar tracker, glucose-aware plans and reports, doctor summary |
| Top-up | ₦800 | +100, never expire | Spent after the monthly credits run out |

## Profit per member per month

"Worst case" means every credit used at its full ₦5 budget. "Typical" is a guess at normal use:
Pro 150 chats and 5 research answers; Plus 250 chats, 10 research, 4 plans and 4 reports; Care
400 chats, 15 research, 4 plans, 4 reports and 2 summaries.

| Plan | Paid | Paystack fee | Worst-case AI | Worst-case profit | Typical AI | Typical profit |
|---|---|---|---|---|---|---|
| Pro monthly | ₦3,000 | ₦145 | ₦1,250 | **₦1,605 (53%)** | ~₦590 | ~₦2,265 (76%) |
| Plus monthly | ₦5,000 | ₦175 | ₦2,500 | **₦2,325 (47%)** | ~₦1,120 | ~₦3,700 (74%) |
| Care monthly | ₦7,000 | ₦205 | ₦3,750 | **₦3,045 (44%)** | ~₦1,720 | ~₦5,070 (72%) |
| Pro yearly (per month) | ₦2,500 | ₦46 | ₦1,250 | **₦1,204 (48%)** | | |
| Plus yearly (per month) | ₦4,167 | ₦71 | ₦2,500 | **₦1,596 (38%)** | | |
| Care yearly (per month) | ₦5,833 | ₦96 | ₦3,750 | **₦1,987 (34%)** | | |
| Top-up | ₦800 | ₦12 | ₦500 | **₦288 (36%)** | | |

Free users cost at most ₦125 a month each (about ₦40 typically). That's the cost of winning
members.

## Fair use

- **Monthly:** when credits run out, the app says so plainly and offers a top-up or an upgrade.
- **Hourly:** at most 40 credits in any rolling hour. After that the app says: "You've used a
  lot of AI in the last hour. To keep it fast for everyone, it'll be ready again in about N
  minutes." The message is true. It never claims a fake server outage, which could breach the
  FCCPA's rules against misleading consumers.

## Where to change things

All of these are in `backend/config/settings.py`:
- `PRO_TIERS`: prices and credits per plan.
- `FREE_MONTHLY_CREDITS`, `CREDIT_TOPUP`.
- `AI_CREDIT_COSTS`: credits per action.
- `AI_CREDITS_PER_HOUR`: the hourly fair-use limit.
- `GEMINI_PRICES_USD_PER_MILLION`, `GEMINI_SEARCH_USD_PER_QUERY`, `USD_NGN_RATE`: for the report.
