#!/bin/sh
# Meeting Organizer Agent - Backend container entrypoint
# Applies database migrations, seeds baseline data, then serves the API.
set -e

cd /app

echo "[entrypoint] applying database migrations..."
alembic upgrade head

echo "[entrypoint] seeding baseline data..."
python -m app.db.seed

echo "[entrypoint] starting uvicorn on ${HOST:-0.0.0.0}:${PORT:-8000}"
exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
