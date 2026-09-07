#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

if [ "$SEED_ON_START" = "true" ]; then
  echo "Seeding dev/test data..."
  python -m app.seed
fi

exec "$@"
