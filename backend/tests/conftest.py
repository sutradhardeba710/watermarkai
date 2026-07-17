"""Pytest configuration."""
import os

# Default to a test-friendly secret + local storage so importing the app
# doesn't require a real environment. Tests can override further.
os.environ.setdefault("VWA_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("VWA_DATABASE_URL", "postgresql+psycopg://vwa:vwa@localhost:5432/vwa_test")
os.environ.setdefault("VWA_REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("VWA_STORAGE_BACKEND", "local")
os.environ.setdefault("VWA_STORAGE_LOCAL_ROOT", "./.storage-test")
