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

The app includes **Light**, **Dark**, and **System** themes. Light is the default;
Dark uses neutral charcoal surfaces with green accents. Change the theme from the
sidebar, **More** on mobile, or **Settings → Appearance**. The choice saves
immediately in this browser; System follows your device's appearance.

Screenshots below use sample data in a local preview.

| Home — light | Home — dark |
|---|---|
| ![Home in light mode](docs/screenshots/home.png) | ![Home in neutral charcoal dark mode](docs/screenshots/home-dark.png) |

| Inventory | Meal history |
|---|---|
| ![Inventory with category icons](docs/screenshots/inventory.png) | ![Meal history with readable recipe details](docs/screenshots/history.png) |

| On a phone — light | On a phone — dark |
|---|---|
| <img src="docs/screenshots/mobile-home.png" alt="Home on mobile in light mode" width="300"> | <img src="docs/screenshots/mobile-home-dark.png" alt="Home on mobile in dark mode" width="300"> |

The editable [design file](design.pen) includes shared light/dark color variables
and refreshed Home screens for desktop and mobile. Imported design assets live in
`images/`; keep that directory alongside the `.pen` file.

## How it works

1. **Onboarding** — set household size, allergies, dietary needs, and equipment.
   Dislikes, pantry staples, complexity, and repeat preferences are optional or can
   be tuned later in Settings.
2. **Inventory** — take a picture of a grocery receipt, an order confirmation, the
   bags on the counter, or a fridge/pantry shelf; AI vision extracts the items,
   quantities, and rough expiry dates. Compare the original photo with the editable list, then confirm it once.
   Unfinished scans are available on the capture page; edits survive reloads in
   this browser.
   You can also add items by hand.
3. **Cook** — type a craving ("something with chicken & spinach") or hit *Surprise
   me* and get recipes you can make right now, with quantities checked against your inventory, consistent cooking-method icons, and a related recipe
   link. Unknown amounts or incompatible units are marked **Check amount**. Meals that use up expiring items
   float to the top; grilled dishes are skipped when the weather says no.
   Choose **Cooking for** on Home or Cook to set the number of people for a request;
   it defaults to household size. Recipes are generated for that count, and a mismatched
   serving count triggers a retry. Weekly plans use the household default.
   Instructions and Cook Mode show contextual reminders for hot cookware, steam,
   boiling liquids, and hot oil, including older saved recipes. These common-hazard
   reminders are not a comprehensive safety check.
   **Cook Mode** saves your step, ingredient checklist, and timer deadlines in this
   browser, so closing or reloading it does not reset your progress.
4. **Plan** — generate a week of distinct meals, swap any day, and turn it into one
   consolidated shopping list. Planning runs in the background with visible progress;
   interrupted jobs keep completed meals and can resume.
5. **Shopping** — a standalone list you can add to by hand, from a plan, or from a
   single meal; check things off and move them straight into inventory. Repeating
   an import is safe; use **Add again** for an intentional second copy.
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
- Optionally, a Brave Search API key — https://brave.com/search/api/ — for
  related recipe links, weather-aware grilling, and delivery search.
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

Ports bind to `127.0.0.1` by default. `FRIDGE_BIND_HOST` overrides that address for
an authenticated deployment behind HTTPS.

To stop: `docker compose down`. Your data lives in `./data/` and survives restarts.

## Configuration (`.env`)

| Variable | Purpose | Default |
|---|---|---|
| `OPENROUTER_API_KEY` | Your OpenRouter key (**required** for AI features) | — |
| `OPENROUTER_VISION_MODEL` | Model for reading fridge photos (must support images) | `openai/gpt-4o-mini` |
| `OPENROUTER_MEAL_MODEL` | Model for meal suggestions | `anthropic/claude-sonnet-4.6` |
| `OPENROUTER_BASE_URL` | OpenAI-compatible API endpoint | `https://openrouter.ai/api/v1` |
| `BRAVE_API_KEY` | Brave Search key — source links, weather, delivery (optional; features skip gracefully without it) | — |
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
| `FRIDGE_BIND_HOST` | Docker host interface for published ports | `127.0.0.1` |
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
cd frontend && npm test && npm run lint && npm run build
cd backend && python -m pytest
```

Frontend tests cover request recovery, dialog focus/error handling, scan draft
restoration, cooking progress/timers, and theme behavior. Backend tests cover
allergen/quantity matching, replay protection, resumable plans, ownership, and
migration compatibility.

For a disposable PostgreSQL preview and integration tests:

```bash
docker compose -f docker-compose.test.yml -p fridge-reliability up --build -d
# Once per fresh test stack:
docker compose -f docker-compose.test.yml -p fridge-reliability exec db \
  psql -U postgres -c 'CREATE DATABASE fridge_test'
docker compose -f docker-compose.test.yml -p fridge-reliability exec \
  -e TEST_DATABASE_URL=postgresql+psycopg://postgres:fridge-test-only@db:5432/fridge_test \
  backend python -m pytest tests/test_migrations.py tests/test_app_smoke.py
```

The preview is at `http://localhost:18080`, API at `http://localhost:18000`.
The test Compose file overrides cloud/database settings and uses synthetic local
accounts. It reads optional AI keys from `.env` for live generation. Its database
and photos are disposable. Stop it with the same Compose command ending in `down`.
**Migration tests wipe `TEST_DATABASE_URL`; never point them at an existing app database.**

Optional live checks load the root `.env` without printing credentials:

```bash
cd backend
python scripts/check_integrations.py                 # read-only service probes
python scripts/check_integrations.py --cloud-only    # temporary accounts + private photo + HTTP isolation
python scripts/check_integrations.py --exercise      # also billable AI vision/meal requests
python scripts/check_integrations.py --scratch-migration  # transactional scratch schema, rolled back
```

Live exercises delete their temporary accounts/photos in a `finally` block and
return a failure if cleanup fails. Scratch migrations never alter the public app
schema. Use the default read-only probe to see the deployed migration revision.

## Database migrations

The schema is managed by Alembic (`backend/alembic/`). The app upgrades to the latest
revision on startup, so `docker compose up` and `uvicorn --reload` both migrate
automatically — including a pre-Alembic `data/fridge.db`. Back up your database
before upgrading a deployed app. After editing
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

- The durable plan worker runs in the shipped single Uvicorn process. Keep one
  backend process/replica; multiple workers require a separate job service.
  Restarted in-progress plans are marked interrupted for explicit resume.
- Allergy filtering covers common ingredient aliases and categories; it cannot
  establish that a dish is allergen-free. Check ingredient labels and preparation.

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
