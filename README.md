# 🧊 Fridge Meal Assistant

An AI-powered, single-user web app that knows what's in your fridge/pantry and your
cooking preferences, and tells you what to make — with a full recipe and step-by-step
instructions. Suggested meals won't repeat within a window you choose.

## How it works

1. **Onboarding** — set allergies, kitchen equipment, dietary restrictions, dislikes,
   meal complexity, and a "don't repeat meals for N days" window.
2. **Inventory** — photograph your fridge/pantry; AI vision extracts the items and
   quantities. Review/correct the list, then confirm it into your inventory.
3. **Cook** — hit "Suggest a meal" and get recipes you can make right now, with
   in-stock vs. shopping-list ingredients flagged.
4. **History** — every suggestion is logged so meals don't repeat; mark meals cooked
   (optionally decrementing inventory).

## Tech

- **Backend:** Python + FastAPI + SQLAlchemy, SQLite database
- **Frontend:** React (Vite), served by nginx
- **AI:** [OpenRouter](https://openrouter.ai) via the OpenAI-compatible API — vision and
  reasoning models are independently swappable via env vars
- **Deployment:** Docker Compose (two containers)

## Prerequisites

- Docker + Docker Compose
- An OpenRouter API key — create one at https://openrouter.ai/keys (pay-as-you-go)

## Quick start

```bash
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY
docker compose up --build
```

Then open **http://localhost:8080**. The API is on http://localhost:8000
(docs at http://localhost:8000/docs).

To stop: `docker compose down`. Your data lives in `./data/` and survives restarts.

## Configuration (`.env`)

| Variable | Purpose | Default |
|---|---|---|
| `OPENROUTER_API_KEY` | Your OpenRouter key (**required**) | — |
| `OPENROUTER_VISION_MODEL` | Model for reading fridge photos (must support images) | `openai/gpt-4o-mini` |
| `OPENROUTER_MEAL_MODEL` | Model for meal suggestions | `anthropic/claude-sonnet-4.6` |
| `MAX_IMAGE_DIM` | Photos are downscaled to this many px (long edge) before upload | `1024` |
| `AI_REQUEST_TIMEOUT` | Seconds before an AI call times out | `90` |

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
cd backend && python -m pytest          # local
docker compose exec backend python -m pytest   # in container
```

## Notes

- **Single user, no login** — there's one preferences profile and one inventory.
- The database schema is created automatically on first startup
  (`SQLAlchemy create_all`); no migration step is needed for this single-user app.
- AI quantity estimates are approximate — that's why every photo extraction goes
  through a review/edit screen before anything is saved.
