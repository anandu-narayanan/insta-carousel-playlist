#!/bin/sh
set -e

PORT_VALUE="${PORT:-8000}"

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting gunicorn on port ${PORT_VALUE}..."
exec gunicorn carousel_app.wsgi:application \
    --bind "0.0.0.0:${PORT_VALUE}" \
    --timeout 300 \
    --workers 1 \
    --threads 4
