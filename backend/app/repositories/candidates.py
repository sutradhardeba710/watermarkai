"""Watermark-candidate repository (SRS DETECT-002..007).

Thin data-access layer over ``WatermarkCandidate`` rows. The detection worker
emits candidates; the route layer lists, fetches, and approves them. Approval
copies a candidate's geometry into a ``WatermarkMask`` (DETECT-007) so the user
can fine-tune it before sending to the Phase 5 inpaint pipeline.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import VideoProject, WatermarkCandidate, WatermarkMask


# Allowed candidate types — mirrors the values written by the detectors.
CANDIDATE_TYPES = {"logo", "text", "timestamp", "overlay"}


def create_candidate(
    db: Session,
    *,
    project_id: str,
    user_id: str,
    candidate_type: str,
    confidence: float,
    bounding_box: dict,
    is_static: bool = True,
    start_time: float | None = None,
    end_time: float | None = None,
    mask_storage_key: str | None = None,
    tracking_data: Optional[dict] = None,
) -> WatermarkCandidate:
    if candidate_type not in CANDIDATE_TYPES:
        # Defensive: a stage mislabel shouldn't silently land in the table.
        raise ValueError(f"unknown candidate_type {candidate_type!r}")
    # Candidate ownership is inherited through VideoProject. The candidate
    # table intentionally has no user_id column.
    del user_id
    row = WatermarkCandidate(
        project_id=project_id,
        candidate_type=candidate_type,
        confidence=float(confidence),
        start_time=start_time,
        end_time=end_time,
        is_static=is_static,
        bounding_box=bounding_box,
        mask_storage_key=mask_storage_key,
        tracking_data=tracking_data,
    )
    db.add(row)
    db.flush()
    return row


def list_candidates(
    db: Session,
    project_id: str,
    *,
    approved_only: bool = False,
) -> list[WatermarkCandidate]:
    stmt = (
        select(WatermarkCandidate)
        .where(WatermarkCandidate.project_id == project_id)
        .order_by(WatermarkCandidate.confidence.desc(), WatermarkCandidate.created_at.asc())
    )
    if approved_only:
        stmt = stmt.where(WatermarkCandidate.user_approved.is_(True))
    return list(db.execute(stmt).scalars())


def get_candidate(db: Session, candidate_id: str) -> WatermarkCandidate | None:
    return db.get(WatermarkCandidate, candidate_id)


def get_candidate_owned(
    db: Session, candidate_id: str, user_id: str
) -> WatermarkCandidate | None:
    stmt = (
        select(WatermarkCandidate)
        .join(VideoProject, VideoProject.id == WatermarkCandidate.project_id)
        .where(
            WatermarkCandidate.id == candidate_id,
            VideoProject.user_id == user_id,
            VideoProject.deleted.is_(False),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def mark_approved(
    db: Session, candidate: WatermarkCandidate, *, approved: bool = True
) -> WatermarkCandidate:
    candidate.user_approved = bool(approved)
    db.flush()
    return candidate


def clear_candidates_for(db: Session, project_id: str) -> int:
    """Idempotent re-analysis — wipe the prior run's candidates before re-emit."""
    rows = db.execute(
        delete(WatermarkCandidate).where(WatermarkCandidate.project_id == project_id)
    )
    db.flush()
    return rows.rowcount or 0


def delete_candidates_for(db: Session, project_id: str) -> int:
    rows = db.execute(
        delete(WatermarkCandidate).where(WatermarkCandidate.project_id == project_id)
    )
    db.flush()
    return rows.rowcount or 0


def candidate_to_mask(
    db: Session,
    project_id: str,
    user_id: str,
    candidate: WatermarkCandidate,
    *,
    width: int,
    height: int,
    tool: str = "rectangle",
    mask_expansion: int = 0,
    mask_feathering: int = 4,
    temporal_smoothing: bool = False,
) -> WatermarkMask:
    """Promote a candidate into a WatermarkMask so the Phase 5 inpaint path
    can run. Bbox-to-geometry conversion lives here, keeping the orchestrator
    focused on ranking (DETECT-007). ``user_id`` is accepted for parity with
    the rest of the repo layer even though the schema doesn't bind masks to a
    specific user (the project's user_id is the owning user anyway)."""
    bb = candidate.bounding_box or {}
    x = float(bb.get("x", 0))
    y = float(bb.get("y", 0))
    w = float(bb.get("w", 0))
    h = float(bb.get("h", 0))
    geometry: dict[str, Any] = {
        "tool": tool,
        "x": x, "y": y, "w": w, "h": h,
        "vertices": [],
    }
    del user_id  # currently unused: masks belong to a project, not a user
    db.query(WatermarkMask).filter(WatermarkMask.project_id == project_id).delete()
    mask = WatermarkMask(
        project_id=project_id,
        tool=tool,
        geometry=geometry,
        width=width,
        height=height,
        mask_expansion=mask_expansion,
        mask_feathering=mask_feathering,
        temporal_smoothing=temporal_smoothing,
        apply_to_entire=True,
        start_time=None,
        end_time=None,
    )
    db.add(mask)
    # approve the candidate so the UI marks it as the "active" pick
    candidate.user_approved = True
    db.flush()
    return mask


__all__ = [
    "CANDIDATE_TYPES",
    "create_candidate",
    "list_candidates",
    "get_candidate",
    "get_candidate_owned",
    "mark_approved",
    "clear_candidates_for",
    "delete_candidates_for",
    "candidate_to_mask",
]
