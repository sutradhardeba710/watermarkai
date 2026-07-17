"""Regression coverage for project-list media URL attachment."""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.projects import _attach_signed_media_urls
from app.schemas.projects import ProjectSummary


class _NoMediaCalls:
    def signed_download_url(self, *_args, **_kwargs):
        raise AssertionError("summary must not mint a preview-only URL")

    def exists(self, *_args, **_kwargs):
        raise AssertionError("summary must not inspect preview variants")


def test_project_summary_skips_detail_only_preview_urls(monkeypatch):
    monkeypatch.setattr("app.storage.factory.get_storage", lambda: _NoMediaCalls())
    summary = ProjectSummary(
        id="project-1",
        title="Example",
        original_filename="example.mp4",
        status="preview_ready",
        created_at=datetime.now(timezone.utc),
    )
    project = SimpleNamespace(
        id="project-1",
        proxy_storage_key=None,
        thumbnail_storage_key=None,
        preview_storage_key="project-1/preview.mp4",
    )

    _attach_signed_media_urls(summary, project)

    assert not hasattr(summary, "preview_url")

def test_concrete_project_actions_precede_artifact_catch_all():
    """The media route must not shadow candidates/jobs/preview endpoints."""
    from app.api.detection import project_router as detection_router
    from app.api.files import router as files_router
    from app.api.preview import router as preview_router
    from app.api.processing import project_router as processing_router
    from app.main import create_app

    included = [
        route.original_router
        for route in create_app().routes
        if hasattr(route, "original_router")
    ]
    catch_all = included.index(files_router)

    assert included.index(preview_router) < catch_all
    assert included.index(processing_router) < catch_all
    assert included.index(detection_router) < catch_all
