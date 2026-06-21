# Agent Factory Backend
# FastAPI + PostgreSQL + DeepSeek AI
#
# Build:  docker build -t agent-factory-backend -f backend/Dockerfile backend/
# Run:    docker run -p 8000:8000 --env-file .env agent-factory-backend

FROM python:3.12-slim AS base

# ── System dependencies ──────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# ── Python environment ───────────────────────────────────────────────
WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ─────────────────────────────────────────────────
COPY . .

# ── Runtime ──────────────────────────────────────────────────────────
EXPOSE 8000

# Run database migrations then start the server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
