FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy all three packages — worker imports prachar-shared and prachar-api
COPY packages/shared /app/packages/shared
COPY apps/api /app/apps/api
COPY apps/workers /app/apps/workers

# Install all three packages so loop.py can import prachar_api.runtime.*
RUN pip install --no-cache-dir -e packages/shared -e apps/api -e apps/workers

RUN playwright install chromium

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["celery", "-A", "prachar_workers.celery_app", "worker", "-l", "info"]
