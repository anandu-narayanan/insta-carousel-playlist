#!/bin/sh
set -e

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting gunicorn on port ${PORT:-8000}..."
exec gunicorn carousel_app.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --timeout 300 \
    --workers 1 \
    --threads 4
