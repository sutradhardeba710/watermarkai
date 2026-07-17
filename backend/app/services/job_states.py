"""Pure PROCESS-002 state-machine, free of ORM imports so unit tests can exercise
it on machines without SQLAlchemy installed (the 32-bit dev box).

The repo layer re-exports :func:`can_transition` from here.
"""
from __future__ import annotations

from enum import Enum


def _member(name: str) -> str:
    """Return the enum-member *value* for a state name. Kept string-based so this
    module is decoupled from the ORM JobState enum (which mirrors these values)."""
    return name


# A frozen set of legal transitions keyed by current-state value. Terminal
# states map to an empty target set. Values match JobState / ProjectStatus.
_TRANSITIONS: dict[str, frozenset[str]] = {
    "created": frozenset({"processing_queued", "cancelled", "failed"}),
    "processing_queued": frozenset({"processing", "analyzing", "cancelled", "failed"}),
    "processing": frozenset({"encoding", "failed", "cancelled"}),
    "encoding": frozenset({"completed", "failed", "cancelled"}),
    "preview_queued": frozenset({"preview_processing", "cancelled", "failed"}),
    "preview_processing": frozenset({"preview_ready", "failed", "cancelled"}),
    "preview_ready": frozenset(),
    "uploaded": frozenset({"analyzing", "preview_queued", "processing_queued", "cancelled", "expired"}),
    "analyzing": frozenset({"awaiting_review", "preview_queued", "processing_queued", "completed", "failed", "cancelled"}),
    "awaiting_review": frozenset({"processing_queued", "preview_queued", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
    "expired": frozenset(),
    "uploading": frozenset({"uploaded", "cancelled", "failed"}),
}


def can_transition_values(current: str, target: str) -> bool:
    return target in _TRANSITIONS.get(current, frozenset())


def can_transition(current: Enum, target: Enum) -> bool:
    """Convenience for callers passing the ORM enum members."""
    return can_transition_values(current.value, target.value)


__all__ = ["can_transition", "can_transition_values"]
