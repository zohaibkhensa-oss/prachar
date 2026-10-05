FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY packages/shared /app/packages/shared
COPY apps/api /app/apps/api
COPY apps/workers /app/apps/workers

RUN pip install --no-cache-dir -e packages/shared -e apps/api -e apps/workers

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "prachar_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
