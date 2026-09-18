# Fridge Chef project guidance

Read [docs/project-notes.md](docs/project-notes.md) for product decisions and open
follow-ups. Consult [CLAUDE.md](CLAUDE.md) for architecture and [README.md](README.md)
for setup. Keep these files aligned when a durable decision changes; use Git and
PRs for session history rather than turning these notes into a running transcript.

## Working preferences

- Run the app and tests in Docker. Do not install host Python/Node dependencies
  or start host development servers just to verify a change. Inspect existing
  containers and images first, but rebuild or mount the current source so tests
  cover the actual changes. Host editing and lockfile maintenance are fine when needed.
- Prefer the isolated `docker-compose.test.yml` stack for live tests. Its database
  and auth configuration are separate from the normal `.env` deployment. Test
  data must not change the user's saved kitchen or cloud account.
- For UI changes, exercise relevant flows in the browser as well as automated
  tests. Check phone-size layouts and both themes when affected. Live AI calls
  use configured paid services; make purposeful requests, not repeated smoke loops.
- Use a non-`main` branch. Check branch and worktree state before editing; preserve
  unrelated changes. When asked to publish, commit, push, and open/update a PR with
  concrete behavior and validation. Never treat an old PR number as proof of current state.
- Track resources created for the task. When temporary testing is finished,
  remove the task's containers, disposable volumes, network, test image tags, and
  temporary files, unless the user asked to keep the preview running. Do not use
  global Docker prune or remove unrelated containers/images/volumes.
- Never put credentials, `.env` contents, personal kitchen data, or auth tokens
  into project notes, logs, commits, or PRs.

## Docker workflow

Run from the repository root. `fridge-dev` below is a disposable Compose project;
check for an existing project/port conflict before starting it.

```sh
# Live preview: UI :18080, API :18000, disposable PostgreSQL :55432
docker compose -f docker-compose.test.yml -p fridge-dev up --build -d

# Backend unit suite, with real service keys disabled and no database dependency
docker compose -f docker-compose.test.yml -p fridge-dev build backend
docker compose -f docker-compose.test.yml -p fridge-dev run --rm --no-deps \
  -e DATABASE_URL=sqlite:///:memory: -e OPENROUTER_API_KEY= -e BRAVE_API_KEY= \
  backend python -m pytest

# Frontend lint/tests/build run in the Node build stage, not the nginx image
docker build --target build -t fridge-app-frontend-checks ./frontend
docker run --rm --network none fridge-app-frontend-checks \
  sh -c 'npm run lint && npm test && npm run build'

# Only after finishing with this disposable preview
docker compose -f docker-compose.test.yml -p fridge-dev down --volumes --remove-orphans
docker image rm fridge-dev-backend:latest fridge-dev-frontend:latest fridge-app-frontend-checks:latest
```

The PostgreSQL migration/smoke tests wipe their target database. Follow the
separate disposable test-database instructions in README; never point them at
the saved preview database or a real kitchen database. Tests import `app` from
the backend working directory (already `/app` in the backend image).

## Engineering constraints

- Preserve both local SQLite/no-login mode and cloud Supabase mode.
- Scope user-owned queries through `CurrentUser` and the ownership helpers;
  preserve idempotent inventory, cooking, shopping, and plan actions.
- Model changes require Alembic migrations. AI prompt text belongs in
  `backend/app/prompts/`. Frontend API calls go through `src/api/client.js`.
- Keep US-customary unit definitions in frontend/backend aligned. Unknown amounts
  must remain unknown, not silently count as sufficient stock.
- `design.pen` is edited only through Pen/Pencil tools, never as text. Normally
  sync affected screens with UI changes. If the connector cannot open the existing
  design, preserve the file and record the deferred work; do not recreate an empty
  canvas over it. The explicitly deferred work is listed in project notes.
