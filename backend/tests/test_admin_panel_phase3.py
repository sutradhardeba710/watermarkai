"""Admin Panel Phase 3 pure-logic tests — job stage timeline + queue/worker
detail schemas (PRD §10–12).

No DB / SQLAlchemy — runs on the 32-bit dev box.
"""
from __future__ import annotations

from app.schemas.admin import (
    AdminJobDetail,
    JobStageStep,
    QueueInfo,
    QueueMetrics,
)
from app.services import admin_service


# ---------------------------------------------------------------------------
# job_stage_timeline (PRD §10.4)
# ---------------------------------------------------------------------------


def test_timeline_in_progress_marks_current_and_pending():
    steps = admin_service.job_stage_timeline("process", "processing")
    states = {s["stage"]: s["state"] for s in steps}
    assert states["created"] == "done"
    assert states["processing_queued"] == "done"
    assert states["processing"] == "current"
    assert states["encoding"] == "pending"
    assert states["completed"] == "pending"


def test_timeline_completed_marks_all_done():
    steps = admin_service.job_stage_timeline("process", "completed")
    assert all(s["state"] == "done" for s in steps)
    assert steps[-1]["stage"] == "completed"


def test_timeline_failed_flags_terminal_step():
    steps = admin_service.job_stage_timeline("process", "failed")
    assert steps[-1]["state"] == "failed"
    assert steps[-1]["stage"] == "failed"
    # earlier steps are all marked done
    assert all(s["state"] == "done" for s in steps[:-1])


def test_timeline_cancelled_terminal():
    steps = admin_service.job_stage_timeline("analyze", "cancelled")
    assert steps[-1]["state"] == "cancelled"


def test_timeline_analyze_pipeline_stages():
    steps = admin_service.job_stage_timeline("analyze", "analyzing")
    stages = [s["stage"] for s in steps]
    assert stages == ["created", "analyzing", "awaiting_review", "completed"]


def test_timeline_unknown_type_uses_default_pipeline():
    steps = admin_service.job_stage_timeline("encode", "processing")
    stages = [s["stage"] for s in steps]
    assert stages == ["created", "processing", "completed"]


def test_timeline_created_state_first_step_current():
    steps = admin_service.job_stage_timeline("process", "created")
    assert steps[0]["state"] == "current"
    assert steps[1]["state"] == "pending"


def test_timeline_status_not_in_pipeline_falls_back():
    # a preview status on a process job — index falls back to 1 (in progress)
    steps = admin_service.job_stage_timeline("process", "preview_ready")
    # should not raise; first step done, second current
    assert steps[0]["state"] == "done"
    assert steps[1]["state"] == "current"


def test_is_terminal_job_state():
    assert admin_service.is_terminal_job_state("completed")
    assert admin_service.is_terminal_job_state("failed")
    assert admin_service.is_terminal_job_state("cancelled")
    assert admin_service.is_terminal_job_state("expired")
    assert not admin_service.is_terminal_job_state("processing")
    assert not admin_service.is_terminal_job_state("created")


# ---------------------------------------------------------------------------
# Phase 3 schemas
# ---------------------------------------------------------------------------


def test_queue_metrics_shape_defaults():
    m = QueueMetrics()
    assert m.queued == 0 and m.active == 0
    assert m.by_state == {}
    assert m.queues == []


def test_queue_metrics_with_breakdown():
    m = QueueMetrics(
        queued=3, active=1, completed_today=5, failed_today=2,
        by_state={"processing": 1, "created": 3},
        queues=[QueueInfo(name="processing", queued=2, active=1, failed_today=1)],
    )
    assert m.queues[0].name == "processing"
    assert m.by_state["created"] == 3


def test_job_stage_step_model():
    step = JobStageStep(stage="processing", state="current", label="Inpainting frames")
    assert step.state == "current"


def test_admin_job_detail_accepts_timeline():
    detail = AdminJobDetail(
        id="j1", project_id="p1", user_id="u1", job_type="process",
        status="processing", progress=42, processing_mode="balanced",
        created_at="2026-01-01T00:00:00Z",
        timeline=[JobStageStep(stage="processing", state="current", label="Inpainting")],
    )
    assert detail.timeline[0].stage == "processing"
    assert detail.project_title is None
