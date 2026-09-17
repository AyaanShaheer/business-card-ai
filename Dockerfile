# ── Stage 1: Build React frontend ───────────────────────────────
FROM node:22-slim AS frontend-build

WORKDIR /app/apps/frontend

COPY apps/frontend/package.json apps/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY apps/frontend/ ./
RUN npm run build


# ── Stage 2: Python application ─────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for psycopg (PostgreSQL driver)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifest and install Python packages
COPY pyproject.toml ./
RUN uv pip install --system --no-cache .

# Copy application code
COPY apps/ ./apps/
COPY packages/ ./packages/
COPY infra/alembic/ ./infra/alembic/
COPY alembic.ini ./

# Copy frontend build output from stage 1
COPY --from=frontend-build /app/apps/frontend/dist ./apps/frontend/dist

# Create local_storage directory for file uploads
RUN mkdir -p /app/local_storage

EXPOSE 80

# Run migrations then start the server
CMD ["sh", "-c", "alembic upgrade head && uvicorn apps.api.main:app --host 0.0.0.0 --port 80"]
