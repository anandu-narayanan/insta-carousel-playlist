FROM python:3.11-slim

# Install system dependencies including ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create media dir
RUN mkdir -p /tmp/media

EXPOSE 8000

# Collect static then start gunicorn (SECRET_KEY is available at runtime via env vars)
CMD python manage.py collectstatic --noinput && \
    gunicorn carousel_app.wsgi:application \
        --bind 0.0.0.0:$PORT \
        --timeout 300 \
        --workers 2 \
        --threads 2

