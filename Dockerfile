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

COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]

