# Contributing

Thanks for your interest! This is a small single-user app, so the process is
deliberately lightweight: open an issue to discuss anything substantial, or
just send a PR for small fixes.

## Dev setup

### With Docker (matches production)

```bash
cp .env.example .env   # optional — the app boots keyless with degraded features
docker compose up --build
```

Frontend at http://localhost:8080, API at http://localhost:8000 (docs at `/docs`).

### Without Docker

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Python 3.12
pip install -r requirements.txt
DATABASE_URL=sqlite:///./dev.db UPLOAD_DIR=./uploads uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev   # http://localhost:5173, proxies /api to :8000
```

## Tests & lint

```bash
cd backend && python -m pytest                 # backend tests (offline, no API keys needed)
docker compose exec backend python -m pytest   # or inside the running container
cd frontend && npm run lint                    # ESLint (0 errors required)
```

Two gotchas:

- **Tests must run from `backend/`** (`cd backend && python -m pytest`). There is
  no `conftest.py`, so running bare `pytest` from the repo root fails with
  `ModuleNotFoundError: No module named 'app'`.
- **`config.py` loads `.env` from the current working directory.** Never run the
  app or tests from the repo root with a real `.env` present, or your real keys
  get picked up.

Note: `pytest` is intentionally in `requirements.txt` (not a separate dev file)
so `docker compose exec backend python -m pytest` works in the shipped image.

## Conventions

- PR titles use `feat:` / `fix:` / `chore:` / `docs:` prefixes — Release Drafter
  labels and categorizes release notes from them.
- Config lives in `backend/app/config.py` (pydantic-settings); document new env
  vars in `.env.example` and the README table.
- AI prompt text lives in `backend/app/prompts/*.md`, not in code.
- The `UNITS` array in `frontend/src/api/client.js` must stay in sync with the
  unit enum in `backend/app/services/units.py`.
- `design.pen` is the Pencil design source for the UI — it's an opaque binary;
  don't try to edit it as text.
