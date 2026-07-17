# AI Video Watermark Detection & Removal System

Authorized video cleanup platform: detect logo/subtitle/timestamp/overlay → manual or
AI mask → temporal-aware inpainting → output preserving original audio.

> MVP build tracking the project's Product Requirements Document and Software
> Requirements Specification. See `../Product Requirements Document.md` and
> `../Software Requirements Specification.md` (or `docs/`) for the source
> requirements.

## Status

Phased build complete through Phase 8. Phase 9 (tests + README) in progress.

- [x] Phase 1 — Repo scaffold, FastAPI shell, health endpoints, storage interface, Celery app, DB models + baseline migration
- [x] Phase 2 — Auth + user dashboard
- [x] Phase 3 — Upload pipeline + metadata + legal confirmation
- [x] Phase 4 — Manual mask editor (canvas)
- [x] Phase 5 — Processing pipeline (OpenCV inpaint + FFmpeg encode)
- [x] Phase 6 — Preview before/after + download
- [x] Phase 7 — AI detection (heuristic + YOLOv8-seg + OCR)
- [x] Phase 8 — Admin + hardening + retention
- [ ] Phase 9 — Tests + README

## Stack

- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind, Canvas mask editor, SSE progress
- **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, argon2, JWT, Celery/Redis
- **Workers:** Celery — combined worker for MVP (detection / processing / encoding queues)
- **Storage:** pluggable — `LocalFsStorage` (default, no Docker) or `MinioStorage`
- **Video:** ffmpeg/ffprobe; OpenCV inpainting (CPU) for MVP reconstruction
- **Detection:** heuristic pre-screen + YOLOv8n-seg + EasyOCR (PaddleOCR optional). See `LICENSE-NOTE.md` — AGPL weights must be resolved before any commercial launch.

## Requirements

- **Python 3.11+** (64-bit recommended; 32-bit works for pure-logic tests only)
- **Node 20+** (for frontend build)
- **PostgreSQL 15**, **Redis 7** (run natively or `docker compose up -d postgres redis`)
- `ffmpeg` and `ffprobe` on PATH

### Python version note

The MVP uses native extensions (`argon2-cffi`, `cryptography`, `greenlet`, `opencv-python`, `ultralytics`) that require 64-bit Python. If you have only 32-bit Python on PATH, the FastAPI app and workers will not start. Pure-logic tests (`pytest --ignore=tests/test_security.py`) still run.

**Recommended:** install 64-bit Python from [python.org](https://www.python.org/downloads/) or via `pyenv-win`.

## Quick start (Windows)

```powershell
# 1. One-command setup (backend venv + frontend deps)
.\scripts\setup.ps1

# 2. Start backend from the repository root (terminal 1)
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000

# 3. Start worker from the repository root (terminal 2)
# On Windows use --pool=solo: the default prefork pool deadlocks with the
# heavy torch/cv2/ultralytics imports, so tasks are received but never run,
# leaving jobs stuck at "queued · 0% (0/0 frames)".
backend\.venv\Scripts\python.exe -m celery -A workers.celery_app worker -Q detection,processing,encoding --pool=solo -l info
# optional: enable beat for retention + metrics
# backend\.venv\Scripts\python.exe -m celery -A workers.celery_app beat -l info

# 4. Start frontend (terminal 3)
cd frontend
npm run dev
```

Open http://localhost:3000 — the initial landing page appears. Register a user, or log in as:

- **Admin:** `admin@vwa.local` (password: seeded in `backend/app/seed.py`)
- **Demo:** `demo@vwa.local`

## Layout

```
video-watermark-ai/
├── frontend/      Next.js app
├── backend/       FastAPI app, models, migrations, storage, settings
├── workers/       Celery worker app + tasks (detection/processing/encoding)
├── ai-models/     Pluggable model interfaces + impls (detector/tracker/inpainter)
├── infrastructure/ (configs, monitoring stubs)
├── scripts/       setup.ps1, seed, model-download helpers
└── docs/          spec docs
```

## Environment variables

Backend config is loaded from env vars prefixed with `VWA_`. Key knobs:

| Variable | Default | Description |
|----------|---------|-------------|
| `VWA_DATABASE_URL` | `postgresql+psycopg://vwa:vwa@localhost:5432/vwa` | SQLAlchemy DB URL |
| `VWA_REDIS_URL` | `redis://localhost:6379/0` | Redis connection for Celery + job events |
| `VWA_STORAGE_BACKEND` | `local` | `local` or `minio` |
| `VWA_STORAGE_LOCAL_ROOT` | `./.storage` | LocalFS storage root |
| `VWA_MINIO_ENDPOINT` | `localhost:9000` | MinIO endpoint |
| `VWA_SECRET_KEY` | (change in prod) | JWT signing key |
| `VWA_MAX_FILE_SIZE_MB` | `500` | Upload size cap |
| `VWA_MAX_DURATION_SECONDS` | `300` | Video duration cap |
| `VWA_RETAIN_OUTPUT_DAYS` | `7` | Output retention window |
| `VWA_YOLO_WEIGHTS` | `yolov8n-seg.pt` | YOLO weights filename (AGPL) |
| `VWA_OCR_PROVIDER` | `easyocr` | OCR backend | `easyocr` or `paddle` |
| `VWA_MAINTENANCE_MODE` | `false` | Block new uploads/processing when true |

Full list: see `backend/app/core/config.py`.

## Testing

### Pure-logic tests (run on any Python 3.11+)

```bash
cd backend
python -m pytest --ignore=tests/test_security.py -q
```

Phase 9 adds:

- `tests/test_units_phase9.py` — validation, metadata parse, NORM args, ownership
- `tests/test_admin_phase8.py` — admin config, retention policy, RECON-008
- `tests/test_integration_phase9.py` — requires DB/Redis/FFmpeg (`VWA_INTEGRATION=1`)
- `tests/test_e2e_phase9.py` — full stack, sample clip (`VWA_E2E=1`, `VWA_SAMPLE_CLIP`)

### Integration / E2E

```bash
VWA_INTEGRATION=1 pytest tests/test_integration_phase9.py
VWA_E2E=1 VWA_SAMPLE_CLIP=sample_10s.mp4 pytest tests/test_e2e_phase9.py
```

### Security tests

`tests/test_security.py` exercises argon2 hashing and JWT logic. Requires
`argon2-cffi`; skipped on 32-bit Python. Run on a 64-bit env with:

```bash
pip install -e .[dev]
pytest tests/test_security.py
```

## Responsible use

The platform is for **authorized video cleanup only**. Users must confirm ownership
before processing (SRS LEGAL-001..004). Uploading copyrighted material without
authorization violates the terms of use.

**Model licensing:** YOLO weights are AGPL-3.0. See `LICENSE-NOTE.md` for obligations
before any commercial or public deployment. Replace with Apache-2.0 weights (e.g.,
RT-DETR) or accept the AGPL terms.

## License

AGPL-3.0 for the codebase. Additional obligations apply to YOLO weights —
see `LICENSE-NOTE.md`.
