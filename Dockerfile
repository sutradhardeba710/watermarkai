# ─── AI Video Watermark — unified production image ───────────────────────────
# Build context: project root (video-watermark-ai/)
# Includes: backend/app, workers/, ai-models/, yolov8n-seg.pt
#
# Roles (set via CMD override in docker-compose.prod.yml):
#   API     → python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
#   Worker  → python -m celery -A workers.celery_app worker -Q detection,processing,encoding
#   Beat    → python -m celery -A workers.celery_app beat
#   Migrate → python -m alembic upgrade head
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

# System deps: ffmpeg for video processing, OpenCV runtime, libpq for psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies (layer-cached unless pyproject.toml changes) ──────────
COPY backend/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir .

# ── Application source ────────────────────────────────────────────────────────
# backend/ contents → /app/  (gives us /app/app/, /app/migrations/, /app/alembic.ini)
COPY backend/ ./

# workers/ → /app/workers/  (celery_app.py, tasks/, common.py, …)
COPY workers/ ./workers/

# ai-models/ → /app/ai-models/  (Detector / Tracker / Inpainter implementations)
COPY ai-models/ ./ai-models/

# YOLO weights (AGPL — see LICENSE-NOTE.md)
COPY yolov8n-seg.pt ./yolov8n-seg.pt

# ── Python path ───────────────────────────────────────────────────────────────
# /app      → resolves workers.celery_app, workers.tasks.*
# (app.*  is importable because /app/app/ exists after COPY backend/ ./)
ENV PYTHONPATH=/app

# Default: run the FastAPI server (overridden in docker-compose per service)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
