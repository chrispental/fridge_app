# 🧊 Fridge Chef

[![CI](https://github.com/chrispental/fridge_app/actions/workflows/ci.yml/badge.svg)](https://github.com/chrispental/fridge_app/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **A side project, not a product.** This started as a way to answer the nightly
> *"what should we eat?"* after a long day — snap a photo of your groceries, a
> receipt, or a fridge shelf so the app knows what you have, say what you're in the
> mood for (or don't), and get a few ideas you can actually cook with what's on
> hand. Along the way it grew a weekly planner, a shopping list, cook-mode timers,
> and optional accounts. It's shared here in case it's useful or fun to hack
> on. Expect rough edges; issues and PRs are welcome (see
> [Contributing](#contributing--security)).

An AI-powered web app that knows what's in your fridge/pantry and your cooking
preferences, and tells you what to make — with a full recipe and step-by-step
instructions. Suggested meals won't repeat within a window you choose.

It runs in one of two modes:

- **Local mode (default)** — single user, no login, SQLite + photos on a Docker
  volume. `docker compose up` with an OpenRouter key and you're cooking.
- **Cloud mode (optional)** — accounts via [Supabase](https://supabase.com) Auth,
  data in Supabase Postgres, photos in Supabase Storage. Same two containers; see
  [Cloud mode with Supabase](#cloud-mode-with-supabase).

> [!WARNING]
> In **local mode there is no authentication**. Run it on your own machine and access
> it at `localhost` only — anyone who can reach the ports can read and change
> everything, including burning through your API keys. If you want to reach the app
> from elsewhere, use cloud mode behind HTTPS.

## Screenshots

| Home — what's for dinner? | Inventory — scanned from a photo |
|---|---|
| ![Home dashboard](docs/screenshots/home.jpg) | ![Inventory grid with photos](docs/screenshots/inventory.jpg) |

| Meal history — every suggestion, with in-stock vs. to-buy | On a phone |
|---|---|
| ![Meal history card](docs/screenshots/history.jpg) | <img src="docs/screenshots/mobile-home.jpg" alt="Home on mobile" width="300"> |

## How it works

1. **Onboarding** — set allergies, kitchen equipment, dietary restrictions, dislikes,
   pantry staples, meal complexity, and a "don't repeat meals for N days" window.
2. **Inventory** — take a picture of a grocery receipt, an order confirmation, the
   bags on the counter, or a fridge/pantry shelf; AI vision extracts the items,
   quantities, and rough expiry dates. Review/correct the list, then confirm it.
   You can also add items by hand.
3. **Cook** — type a craving ("something with chicken & spinach") or hit *Surprise
   me* and get recipes you can make right now, with in-stock vs. missing ingredients
   flagged, a photo, and a link to the source recipe. Meals that use up expiring items
   float to the top; grilled dishes are skipped when the weather says no.
   **Cook Mode** walks you through the steps with timers.
4. **Plan** — generate a week of distinct meals, swap any day, and turn it into one
   consolidated shopping list.
5. **Shopping** — a standalone list you can add to by hand, from a plan, or from a
   single meal; check things off and move them straight into inventory.
6. **History & Insights** — every suggestion is logged so meals don't repeat; mark
   meals cooked (optionally decrementing inventory), rate them, and feedback shapes
   future suggestions. One meal a week can be marked "order delivery instead".

## Tech

- **Backend:** Python + FastAPI + SQLAlchemy (Alembic migrations) — SQLite by default,
  Postgres in cloud mode
- **Accounts (optional):** [Supabase](https://supabase.com) Auth + Postgres + Storage —
  see *Cloud mode with Supabase* below. Without it the app is single-user with no login.
- **Frontend:** React (Vite), served by nginx
- **AI:** [OpenRouter](https://openrouter.ai) via the OpenAI-compatible API — vision and
  reasoning models are independently swappable via env vars
- **Deployment:** Docker Compose (two containers)

## Prerequisites

- Docker + Docker Compose
- An OpenRouter API key — create one at https://openrouter.ai/keys (pay-as-you-go)
- Optionally, a Brave Search API key — https://brave.com/search/api/ — for recipe
  photos, "view full recipe" links, weather-aware grilling, and delivery search.
  Without it those extras are silently skipped; suggestions still work.

## Quick start

```bash
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY
docker compose up --build
```

Then open **http://localhost:8080**. The API is on http://localhost:8000
(docs at http://localhost:8000/docs). This is local mode — no login; for accounts,
see [Cloud mode with Supabase](#cloud-mode-with-supabase).

To stop: `docker compose down`. Your data lives in `./data/` and survives restarts.

## Configuration (`.env`)

| Variable | Purpose | Default |
|---|---|---|
| `OPENROUTER_API_KEY` | Your OpenRouter key (**required** for AI features) | — |
| `OPENROUTER_VISION_MODEL` | Model for reading fridge photos (must support images) | `openai/gpt-4o-mini` |
| `OPENROUTER_MEAL_MODEL` | Model for meal suggestions | `anthropic/claude-sonnet-4.6` |
| `OPENROUTER_BASE_URL` | OpenAI-compatible API endpoint | `https://openrouter.ai/api/v1` |
| `BRAVE_API_KEY` | Brave Search key — recipe photos, source links, weather, delivery (optional; features skip gracefully without it) | — |
| `BRAVE_COUNTRY` | Country bias for Brave results (ISO 3166-1 alpha-2) | `US` |
| `BRAVE_BASE_URL` | Brave Search API endpoint | `https://api.search.brave.com/res/v1` |
| `BRAVE_REQUEST_TIMEOUT` | Seconds before a Brave call times out | `10` |
| `WEATHER_CACHE_TTL` | Seconds to cache a location's weather lookup | `3600` |
| `MAX_IMAGE_DIM` | Photos are downscaled to this many px (long edge) before upload | `1024` |
| `AI_REQUEST_TIMEOUT` | Seconds before an AI call times out | `90` |
| `DATABASE_URL` | SQLAlchemy database URL (SQLite file, or Supabase Postgres in cloud mode) | `sqlite:////app/data/fridge.db` |
| `UPLOAD_DIR` | Where uploaded photos are stored (local mode) | `/app/data/uploads` |
| `SUPABASE_URL` | Supabase project URL. **Setting this switches on cloud mode** (login required) | — |
| `SUPABASE_SECRET_KEY` | Supabase secret key (`sb_secret_…`) — backend only, used for Storage | — |
| `SUPABASE_STORAGE_BUCKET` | Private bucket for uploaded photos | `fridge-photos` |
| `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` | Same project + publishable key (`sb_publishable_…`), baked into the frontend build | — |
| `BLOB_BACKEND` | `auto` (Supabase in cloud mode, disk otherwise), `local`, or `supabase` | `auto` |
| `LOCAL_USER_ID` | Fixed user id in local mode — don't change after first run | `00000000-…-000000000001` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:5173,http://localhost:8080` |

Swap models freely — that's the point of OpenRouter. Browse slugs at
https://openrouter.ai/models.

## Local development (without Docker)

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL=sqlite:///./dev.db UPLOAD_DIR=./uploads uvicorn app.main:app --reload
```
Frontend:
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api to :8000
```

## Tests

```bash
cd backend && python -m pytest          # local (SQLite)
docker compose exec backend python -m pytest   # in container

# Migration + HTTP smoke tests against a real Postgres (CI does this too):
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/fridge \
  python -m pytest tests/test_migrations.py tests/test_app_smoke.py
```

## Database migrations

The schema is managed by Alembic (`backend/alembic/`). The app upgrades to the latest
revision on startup, so `docker compose up` and `uvicorn --reload` both migrate
automatically — including a pre-Alembic `data/fridge.db`. After editing
`backend/app/models.py`:

```bash
cd backend
DATABASE_URL=sqlite:///./dev.db alembic revision --autogenerate -m "describe change"
# review the generated file in alembic/versions/, then
python -m pytest tests/test_migrations.py   # fails until head matches the models
```

## Cloud mode with Supabase

By default the app is **single-user with no login**: SQLite in `./data`, photos on
disk. Set a few variables and the same containers become multi-user, backed by
[Supabase](https://supabase.com) (Postgres + Auth + Storage). The Free plan works for
trying it out (note: free projects pause after 7 idle days; Pro is $25/mo for
always-on).

1. **Create a project** at https://supabase.com/dashboard and pick a database password.
2. **Enable JWT signing keys**: *Project Settings → JWT Keys → Migrate to asymmetric
   keys* (the backend verifies ES256 tokens against the project's JWKS; legacy HS256
   projects are rejected).
3. **Copy the keys** from *Project Settings → API Keys*: the **publishable** key
   (`sb_publishable_…`, safe in the browser) and a **secret** key (`sb_secret_…`,
   backend only).
4. **Database URL**: *Connect → Session pooler* (port 5432, IPv4-friendly). Use it as
   `DATABASE_URL` with the `postgresql+psycopg://` scheme and `?sslmode=require`.
   The direct `db.<ref>.supabase.co` host is IPv6-only unless you buy the IPv4 add-on.
5. **Storage**: *Storage → New bucket* → name `fridge-photos`, **private**.
6. **Auth URLs**: *Authentication → URL Configuration* → add `http://localhost:8080`
   (and your real origin) to *Site URL / Redirect URLs* so magic links come back to
   the app. Email confirmation is on by default for sign-ups.
7. **Lock down the REST API** (recommended): the migrations enable row-level security
   with no policies, so Supabase's auto-generated REST API denies everything — the
   backend, which connects as the table owner, is unaffected. For belt-and-braces,
   remove `public` from *Project Settings → API → Exposed schemas*.
8. Fill in the *Cloud mode* block in `.env` (`SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
   `DATABASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`) and run
   `docker compose up --build`. The `VITE_*` values are baked into the frontend image,
   so changing them needs a rebuild.

Existing rows in a SQLite database are not migrated to Supabase; cloud mode starts
with an empty database and each account gets its own inventory, preferences, meal
history, plans, and shopping list.

## Notes

- **Local mode is single-user with no login** — one preferences profile, one inventory.
  Cloud mode (above) adds accounts.
- The schema is migrated automatically on startup (Alembic) — see *Database migrations*.
- AI quantity estimates are approximate — that's why every photo extraction goes
  through a review/edit screen before anything is saved.

## Contributing & security

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup and conventions, and
[SECURITY.md](SECURITY.md) for the threat model and how to report vulnerabilities.

## License

[MIT](LICENSE)
