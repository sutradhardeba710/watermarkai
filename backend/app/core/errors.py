"""Standard error envelope (SRS BE-004).

Only the AppError type lives here so pure-logic helpers (app.core.tokens) can
import it without pulling FastAPI. Request-level exception handlers live in
app.core.error_handlers.
"""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)
