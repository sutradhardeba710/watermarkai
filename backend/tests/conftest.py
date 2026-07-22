"""Pytest configuration."""
import os
import sys
from pathlib import Path

# The `workers` package lives at the repo root (one level above backend/), same
# as in the Docker images where both are on PYTHONPATH. Make it importable so
# email-dispatch code paths (app -> workers.tasks.notifications) can be tested.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Default to a test-friendly secret + local storage so importing the app
# doesn't require a real environment. Tests can override further.
os.environ.setdefault("VWA_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("VWA_DATABASE_URL", "postgresql+psycopg://vwa:vwa@localhost:5432/vwa_test")
os.environ.setdefault("VWA_REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("VWA_STORAGE_BACKEND", "local")
os.environ.setdefault("VWA_STORAGE_LOCAL_ROOT", "./.storage-test")
