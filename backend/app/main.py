"""FastAPI application factory."""
from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from slowapi import Limiter
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.detection import candidate_router as detection_candidate_router
from app.api.detection import project_router as detection_project_router
from app.api.files import router as files_router
from app.api.health import router as health_router
from app.api.masks import router as masks_router
from app.api.payments import router as payments_router, credits_router, plans_router
from app.api.preview import router as preview_router
from app.api.processing import jobs_router as jobs_router
from app.api.processing import project_router as processing_project_router
from app.api.projects import router as projects_router
from app.api.uploads import router as uploads_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.error_handlers import (
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException

settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=["300 per minute"])


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        # SRS BE-006 request logging (no sensitive payload logged)
        print(f"req_id={request_id} method={request.method} path={request.url.path} status={response.status_code} ms={elapsed_ms:.1f}")
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # PRD §26.6 — enforce admin-configured maintenance mode (503 for
    # non-exempt traffic while enabled). Added FIRST (innermost) so the 503
    # response still passes through CORSMiddleware and RequestIdMiddleware —
    # browsers must be able to read the maintenance payload cross-origin.
    from app.core.maintenance import MaintenanceMiddleware
    app.add_middleware(MaintenanceMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    # slowapi (BE-007 rate limiting)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(health_router)
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(projects_router, prefix=settings.api_prefix)
    app.include_router(uploads_router, prefix=settings.api_prefix)
    app.include_router(masks_router, prefix=settings.api_prefix)
    # Register every concrete project action before files_router. files defines
    # a catch-all /projects/{project_id}/{kind}; placing it earlier would make
    # paths such as /candidates and /jobs fail as "Unknown artifact kind."
    app.include_router(preview_router, prefix=settings.api_prefix)
    app.include_router(processing_project_router, prefix=settings.api_prefix)
    app.include_router(jobs_router, prefix=settings.api_prefix)
    app.include_router(detection_project_router, prefix=settings.api_prefix)
    app.include_router(detection_candidate_router, prefix=settings.api_prefix)
    app.include_router(files_router, prefix=settings.api_prefix)
    app.include_router(admin_router, prefix=settings.api_prefix)
    app.include_router(payments_router, prefix=settings.api_prefix)
    app.include_router(credits_router, prefix=settings.api_prefix)
    app.include_router(plans_router, prefix=settings.api_prefix)

    @app.get("/")
    def root() -> dict:
        return {"name": settings.app_name, "version": "0.1.0", "docs": "/docs"}

    @app.on_event("startup")
    def _seed_plans() -> None:
        """Ensure the plan catalog rows exist in the database on every startup."""
        try:
            from app.core.db import SessionLocal
            from app.services.payment_service import seed_plans
            with SessionLocal() as db:
                seed_plans(db)
                db.commit()
        except Exception as exc:  # noqa: BLE001 — DB may not exist in CI
            import logging as _log
            _log.getLogger(__name__).warning("Plan seed skipped: %s", exc)

    return app


app = create_app()
