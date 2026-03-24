web: gunicorn carousel_app.wsgi:application --bind 0.0.0.0:$PORT --timeout 300 --workers 2
worker: celery -A carousel_app worker --loglevel=info --concurrency=2
