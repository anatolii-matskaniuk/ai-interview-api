#!/bin/sh

echo "Waiting for PostgreSQL to be ready..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "PostgreSQL is ready!"

echo "Applying database migrations..."
alembic upgrade head

echo "Starting FastAPI server..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
