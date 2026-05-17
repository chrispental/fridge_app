#!/bin/sh
set -e

# Ensure the mounted data directories exist (DB file + uploaded images).
mkdir -p /app/data /app/data/uploads

# The DB schema is created on app startup (SQLAlchemy create_all).
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
