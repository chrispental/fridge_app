#!/bin/sh
set -e

# Ensure the mounted data directories exist (DB file + uploaded images).
mkdir -p /app/data /app/data/uploads

# Alembic migrations run on app startup (see app/main.py lifespan).
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
