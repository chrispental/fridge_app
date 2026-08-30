# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An AI app that suggests meals from fridge/pantry inventory and user preferences.
FastAPI + SQLAlchemy backend, React/Vite frontend, AI via OpenRouter, deployed with
Docker Compose. Brave Search enriches suggestions (recipe photo + source link), gates
grilling on live weather, and powers the once-a-week delivery lookup.

It runs in one of two modes, chosen by whether `SUPABASE_URL` is set:

- **Local mode (default):** single user, no login, SQLite file + photos on the `data/`
  volume. `docker compose up` with only AI keys must always keep working.
- **Cloud mode:** multi-user. Supabase Auth (JWT verified server-side), Supabase
  Postgres, Supabase Storage for photos. Backend/frontend still run in this repo's
  Docker Compose; only the data/auth services are Supabase's.

## Commands

```bash
# Run the whole stack (needs .env with OPENROUTER_API_KEY + BRAVE_API_KEY — see .env.example)
docker compose up --build          # frontend :8080, backend :8000 (docs at /docs)
docker compose down

# Backend tests (SQLite)
cd backend && python -m pytest                 # all
python -m pytest tests/test_units.py            # one file
python -m pytest tests/test_units.py::test_normalize_known_units   # one test
docker compose exec backend python -m pytest    # inside the running container
# Migration + HTTP smoke tests against real Postgres (CI runs this too)
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/fridge \
  python -m pytest tests/test_migrations.py tests/test_app_smoke.py

# Migrations (Alembic). The app upgrades to head on startup; the CLI is for authoring.
cd backend && DATABASE_URL=sqlite:///./dev.db alembic revision --autogenerate -m "..."
cd backend && DATABASE_URL=sqlite:///./dev.db alembic upgrade head

# Local dev (without Docker)
cd backend && DATABASE_URL=sqlite:///./dev.db UPLOAD_DIR=./uploads uvicorn app.main:app --reload
cd frontend && npm install && npm run dev        # :5173, proxies /api to :8000
cd frontend && npm run lint
```

The frontend has ESLint (flat config) but no test suite. There is no Python linter.

## Architecture

**Auth seam — `backend/app/auth.py`.** Every endpoint takes `user: CurrentUser`
(`Annotated[AuthUser, Depends(get_current_user)]`). In local mode that resolves to the
fixed `settings.local_user_id` with no header at all; in cloud mode the request must carry
`Authorization: Bearer <Supabase access token>`, verified **locally** against the project
JWKS (`PyJWKClient`, ES256/RS256 only — legacy HS256 projects are rejected) with
`aud=authenticated` and `iss={SUPABASE_URL}/auth/v1`. The `users` row is upserted on
first sight. `/api/health` and `/docs` are the only unauthenticated routes. Routers never
branch on the mode.

**Per-user scoping — `backend/app/services/scope.py`.** The one place that knows how
ownership is enforced: `get_prefs(db, user_id)` (get-or-create, seeds default staples —
there is no longer a singleton `id=1` row), `inventory_for`, `staples_for`, and
`get_owned(db, Model, id, user_id, label=…)` which 404s (not 403s) on rows belonging to
someone else. Every user-owned table has a `user_id` (`String(36)`, indexed; unique on
`preferences`); `meal_plan_entries` is scoped through its parent plan. **Every new model
gets `user_id`; every new query filters on it; every new endpoint takes `CurrentUser`.**
`meal_engine` functions take `user_id` as an explicit positional argument.

**Database + migrations.** SQLAlchemy models in `app/models.py` are the source of truth;
**Alembic owns the `public` schema** (`backend/alembic/`, `app/migrations.py`). `lifespan`
runs `run_migrations()` on every start, so pre-Alembic `data/fridge.db` files upgrade in
place (revision `0001` is idempotent for that reason). `tests/test_migrations.py::
test_head_matches_models` fails whenever `models.py` changes without a revision — write one
with `alembic revision --autogenerate` and review it (SQLite needs batch mode, already
configured in `env.py`; name any new FK constraint explicitly). Unit tests still use
`create_all` on in-memory SQLite for speed; `test_create_all_matches_head` keeps that
honest. Don't insert explicit integer primary keys (Postgres sequences won't advance).
On Postgres, RLS is **enabled with no policies** on every table: the backend connects as
the table owner and is unaffected, while Supabase's auto-generated REST API (reachable
with the publishable key that ships in the browser bundle) is denied outright. If tables
are ever exposed to the browser via PostgREST, real policies come first.

**Connection.** `app/database.py` builds the engine from `DATABASE_URL`: SQLite gets
`check_same_thread=False`; Postgres gets a small pool with `pool_pre_ping` (the Supavisor
pooler and paused free-tier projects drop idle connections). Cloud installs should use the
Supavisor **session** pooler (port 5432); the direct host is IPv6-only, and transaction
mode (6543) breaks psycopg prepared statements.

**Photo storage — `backend/app/services/blob_storage.py`.** `get_blob_storage()` returns
`LocalDiskStorage` (files under `UPLOAD_DIR`; tolerates legacy absolute paths) or
`SupabaseStorage` (private bucket, key `<user_id>/<uuid>.jpg`, plain `httpx` against the
Storage REST API with the secret key). `ExtractionBatch.image_key` is opaque; the
client-facing URL is always `/api/inventory/extract/{id}/image`, which 302s to a
short-lived signed URL when the backend can mint one, else streams the bytes. Unlike
Brave, storage is **not** fail-soft — a failed upload is a 502 from `/extract`.
`services/vision.preprocess()` is pure (bytes in, JPEG bytes + data URL out).

**AI access — `backend/app/services/ai_client.py`.** Every AI call goes through
`call_structured()`, which uses the `openai` SDK pointed at OpenRouter. OpenRouter
routes to many providers with uneven structured-output support, so it runs a fallback
ladder: `json_schema` → `json_object` → plain → one repair retry. Two models are
configured independently via env vars (`OPENROUTER_VISION_MODEL`,
`OPENROUTER_MEAL_MODEL`). OpenRouter model slugs go stale — verify against
`https://openrouter.ai/api/v1/models` before changing a default.

**Photo → inventory is a two-step extract/confirm flow.** `POST /inventory/extract`
downscales the image (Pillow), stores it via blob storage, calls the vision model,
creates an `ExtractionBatch` (`pending_review`), and returns proposed items **without
persisting them**. `POST /inventory/extract/{id}/confirm` persists the user-reviewed
list. AI quantity estimates are unreliable by design — the human review step is the
safeguard.

**Meal suggestion — `backend/app/services/meal_engine.py`.** `suggest_meals(db, user_id, …)`
builds a prompt from preferences + inventory + recent meal titles, then enforces three
rules **server-side after the AI responds** (the LLM's compliance is only a hint):
the allergy filter, the no-repeat window (prompt instruction + fuzzy `difflib`
post-filter on normalized titles), and the **grill gate** (drop suggestions whose
`cooking_method`/title/steps look grilled when the weather is bad — see below). Every
returned suggestion is logged as a `Meal` row immediately, so the no-repeat window
applies even to un-cooked suggestions. Each kept suggestion is then enriched with a
Brave photo + source link via `_enrich_with_brave()` before persistence.

**Brave Search — `backend/app/services/brave_search.py`.** Singleton `httpx` client,
keyed by `BRAVE_API_KEY`. `search_web()` and `search_image()` are **fail-soft by
contract** — any error (network, non-200, response shape) is logged and returned as
`[]`/`None`, so suggestion and delivery never hard-fail when Brave is unavailable. Used
for recipe photos, "view full recipe" links, the weather snippet, and delivery order links.

**Weather grill gate — `backend/app/services/weather.py`.** Brave has no weather endpoint,
so `get_weather(location)` web-searches the forecast and keyword-scans the snippet for
precipitation (negation-aware, e.g. "no rain" doesn't trip it); winter is derived
deterministically from the month. It **fails open** (ambiguity → grill allowed) because
this is a soft convenience, not a safety rule. Results are cached in-memory per location
(`WEATHER_CACHE_TTL`). The gate is skipped entirely when `Preferences.location` is empty.

**Weekly delivery — routes in `backend/app/routers/meals.py`.** One meal per rolling
7-day window **per user** can be marked ordered for delivery. State lives on the `Meal`
row (`delivery_ordered_at` + `status="ordered"`); `most_recent_delivery(db, user_id)`
enforces the quota. `POST /meals/{id}/order-delivery` returns 422 if no location is set,
409 if the weekly slot is used, else stamps the order and stores Brave order links in
`recipe_json["delivery_options"]`. `GET /meals/delivery/status` reports
`{used, remaining, next_available_at}` — declared **before** the dynamic `/{meal_id}`
route so the path isn't captured as an id.

**Units — `backend/app/services/units.py`.** US customary, a fixed enum. `normalize_unit`
maps free-text to the canonical set; metric units normalize to `"unknown"` rather than
being relabeled (relabeling would lie about the amount). `try_subtract` does best-effort
inventory decrement when a meal is marked cooked. **The `UNITS` array in
`frontend/src/api/client.js` must stay in sync with this enum.**

**Prompts** are markdown files in `backend/app/prompts/`, loaded by
`services/prompts.py` — edit those rather than embedding prompt text in code.

**Frontend.** React Router; all API calls go through the single wrapper in
`src/api/client.js`, which attaches `Authorization: Bearer` when `AuthProvider` has
installed a token getter and signs the user out on a 401. `src/auth/supabase.js` creates
the supabase-js client only when `VITE_SUPABASE_URL` + `VITE_SUPABASE_PUBLISHABLE_KEY`
were present at build time (`AUTH_ENABLED`); those are Docker build args in
`docker-compose.yml`, so changing them needs a rebuild. `App.jsx` gates in order:
session (cloud mode only → `pages/Login.jsx`) → onboarding → app; the onboarding status
query is `enabled` only once signed in so a 401 is never read as "not onboarded".
`AuthProvider` clears the React Query cache on sign-out / account switch. The dark theme
is driven entirely by CSS variables in `src/index.css`; the responsive nav is one
component (`Nav.jsx`, which shows the account email and a sign-out control in cloud
mode) that CSS renders as a desktop sidebar or a mobile bottom pill bar. `MealCard.jsx`
renders the Brave photo, cooking-method chip, source link, and the "Order delivery"
button (gated on the weekly quota fetched by the page); the location field lives in
`PreferencesForm.jsx`.

## Conventions

- Config is centralized in `backend/app/config.py` (pydantic-settings).
  `OPENROUTER_API_KEY` and `BRAVE_API_KEY` are required for full functionality; the
  Supabase settings are optional and switch on cloud mode; everything else has a
  sensible default. `SUPABASE_SECRET_KEY` is backend-only — never a `VITE_` var or a
  Docker build arg.
- `design.pen` is a Pencil design file — open it with the Pencil tools, never as text.
  **Keep it in sync with the frontend:** whenever you change UI in `frontend/src`, make
  the matching update in `design.pen` (components and the affected screens) in the same
  change.
