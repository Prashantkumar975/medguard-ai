# MedGuard AI backend image — serves the API, and runs Celery worker/beat.
FROM python:3.12-slim

# Playwright chromium runtime libs (for JS-rendered pages). Remove if unused.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install the Playwright browser at build time so JS rendering works in-container.
RUN python -m playwright install --with-deps chromium || true

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY scripts ./scripts

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Default: API server. Override the command for worker/beat in compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
