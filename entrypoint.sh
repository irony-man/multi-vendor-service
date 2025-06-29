#!/bin/sh
# This script waits for database services to be ready, validates the Django app,
# and then starts the application.

# Wait for the database services to be available.
echo "Waiting for database services..."
until python /app/healthcheck.py; do
  >&2 echo "Services are unavailable - sleeping"
  sleep 1
done
>&2 echo "Services are up."

# Run Django's internal checks to find any configuration errors.
# This will fail fast if there's a problem with the app itself.
echo "Running Django checks..."
python manage.py check || exit 1 # Exit if checks fail

echo "Django checks passed. Starting Gunicorn server..."

# Execute the command passed to this script
exec "$@"
