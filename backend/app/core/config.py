"""Application configuration loaded from environment via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this module (backend/.env) so it loads regardless of
# the CWD uvicorn was started from. A bare "env_file='.env'" is CWD-relative and
# silently no-ops when the process is launched from the repo root with
# --app-dir backend, which left storage/secret defaults diverged from backend/.env.
# config.py lives at backend/app/core/config.py — three parents up reaches backend/.
_ENV_FILE = str(Path(__file__).resolve().parent.parent.parent / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VWA_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "AI Video Cleanup Studio"
    environment: str = "dev"  # dev | staging | prod
    api_prefix: str = "/api/v1"
    secret_key: str = "change-me-in-production-please-use-a-long-random-string"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Google Sign-In (Google Identity Services) ---
    # OAuth 2.0 Client ID from console.cloud.google.com > APIs & Services >
    # Credentials. Used as the expected `aud` when verifying ID tokens — leave
    # blank to keep /auth/google disabled.
    google_client_id: str = ""

    # --- Database ---
    database_url: str = "postgresql+psycopg://vwa:vwa@localhost:5432/vwa"

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Storage ---
    # local | minio
    storage_backend: str = "local"
    storage_local_root: str = "./.storage"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket_prefix: str = "vwa-"

    # --- Upload limits (SRS UPLOAD-003) ---
    max_file_size_mb: int = 500
    max_duration_seconds: int = 300
    max_width: int = 1920
    max_height: int = 1080
    max_fps: int = 60
    allowed_upload_extensions: list[str] = ["mp4", "mov", "webm"]
    allowed_upload_mime: list[str] = [
        "video/mp4",
        "video/quicktime",
        "video/webm",
    ]

    # --- Output / retention (SRS STORAGE-006) ---
    output_codec: str = "libx264"
    output_pixel_format: str = "yuv420p"
    output_audio_codec: str = "aac"
    retain_original_hours: int = 24
    retain_preview_hours: int = 24
    retain_output_days: int = 7
    retain_failed_hours: int = 6

    # --- Signed URL ---
    signed_url_expire_minutes: int = 30

    # --- Worker ---
    job_timeout_seconds: int = 1800
    max_retries: int = 2
    worker_concurrency: int = 2

    # --- Email (console stub for MVP) ---
    smtp_console: bool = True
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@vwa.local"
    app_base_url: str = "http://localhost:3000"

    # --- Razorpay (Phase 6 billing) ---
    razorpay_key_id: str = ""            # rzp_test_XXXX or rzp_live_XXXX
    razorpay_key_secret: str = ""        # keep secret — never expose client-side
    razorpay_webhook_secret: str = ""    # set in Razorpay dashboard Webhook settings
    # Razorpay plan IDs for paid tiers (created in Razorpay dashboard once)
    razorpay_plan_id_starter: str = ""  # e.g. plan_XXXXXXXXX
    razorpay_plan_id_pro: str = ""       # e.g. plan_XXXXXXXXX

    # --- FFprobe / FFmpeg ---
    ffprobe_bin: str = "ffprobe"
    ffmpeg_bin: str = "ffmpeg"

    # --- Detection ---
    detection_sample_fps: float = 1.0
    detection_min_samples: int = 10
    detection_max_samples: int = 200
    detection_confidence_threshold: float = 0.25
    yolo_weights: str = "yolov8n-seg.pt"
    ocr_provider: str = "easyocr"  # easyocr | paddle | none

    @property
    def storage_local_path(self) -> Path:
        p = Path(self.storage_local_root).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
