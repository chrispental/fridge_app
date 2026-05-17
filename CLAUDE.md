# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-user (no auth) AI app that suggests meals from fridge/pantry inventory and
user preferences. FastAPI + SQLite backend, React/Vite frontend, AI via OpenRouter,
deployed with Docker Compose.

## Commands

```bash
# Run the whole stack (needs .env with OPENROUTER_API_KEY — see .env.example)
docker compose up --build          # frontend :8080, backend :8000 (docs at /docs)
docker compose down

# Backend tests
cd backend && python -m pytest                 # all
python -m pytest tests/test_units.py            # one file
python -m pytest tests/test_units.py::test_normalize_known_units   # one test
docker compose exec backend python -m pytest    # inside the running container

# Local dev (without Docker)
cd backend && DATABASE_URL=sqlite:///./dev.db UPLOAD_DIR=./uploads uvicorn app.main:app --reload
cd frontend && npm install && npm run dev        # :5173, proxies /api to :8000
```

There is no linter configured. The frontend has no test suite.

## Architecture

**AI access — `backend/app/services/ai_client.py`.** Every AI call goes through
`call_structured()`, which uses the `openai` SDK pointed at OpenRouter. OpenRouter
routes to many providers with uneven structured-output support, so it runs a fallback
ladder: `json_schema` → `json_object` → plain → one repair retry. Two models are
configured independently via env vars (`OPENROUTER_VISION_MODEL`,
`OPENROUTER_MEAL_MODEL`). OpenRouter model slugs go stale — verify against
`https://openrouter.ai/api/v1/models` before changing a default.

**Photo → inventory is a two-step extract/confirm flow.** `POST /inventory/extract`
downscales the image (Pillow), calls the vision model, creates an `ExtractionBatch`
(`pending_review`), and returns proposed items **without persisting them**.
`POST /inventory/extract/{id}/confirm` persists the user-reviewed list. AI quantity
estimates are unreliable by design — the human review step is the safeguard.

**Meal suggestion — `backend/app/services/meal_engine.py`.** `suggest_meals()` builds a
prompt from preferences + inventory + recent meal titles, then enforces two rules
**server-side after the AI responds** (the LLM's compliance is only a hint):
the allergy filter, and the no-repeat window (prompt instruction + fuzzy
`difflib` post-filter on normalized titles). Every returned suggestion is logged as a
`Meal` row immediately, so the no-repeat window applies even to un-cooked suggestions.

**Units — `backend/app/services/units.py`.** US customary, a fixed enum. `normalize_unit`
maps free-text to the canonical set; metric units normalize to `"unknown"` rather than
being relabeled (relabeling would lie about the amount). `try_subtract` does best-effort
inventory decrement when a meal is marked cooked. **The `UNITS` array in
`frontend/src/api/client.js` must stay in sync with this enum.**

**Database.** SQLAlchemy + SQLite. Schema is created on startup via
`Base.metadata.create_all` (no Alembic) and a singleton `Preferences` row (id=1) is
seeded — see the `lifespan` handler in `app/main.py`. The DB file and uploaded images
live in `data/` (a Docker volume, gitignored).

**Prompts** are plain-text files in `backend/app/prompts/`, loaded by
`services/prompts.py` — edit those rather than embedding prompt text in code.

**Frontend.** React Router; all API calls go through the single wrapper in
`src/api/client.js`. `App.jsx` gates on onboarding status. The dark theme is driven
entirely by CSS variables in `src/index.css`; the responsive nav is one component
(`Nav.jsx`) that CSS renders as a desktop sidebar or a mobile bottom pill bar.

## Conventions

- Config is centralized in `backend/app/config.py` (pydantic-settings). Only
  `OPENROUTER_API_KEY` is required; everything else has a sensible default.
- `design.pen` is a Pencil design file — open it with the Pencil tools, never as text.
