"""Email service: template rendering, async dispatch, and console delivery.

Hermetic — no DB/Redis/broker/SMTP. Verifies render output, that queue_email
hands off to the resilient Celery publisher on the processing queue, that a
broker failure is swallowed (a notification must never break its caller), and
that the console-delivery branch works without touching the network.
"""
from __future__ import annotations

import pytest

from app.services import email_service


ALL_TEMPLATES = {
    "welcome_verify": {"name": "Ada", "verify_url": "https://app.example/verify-email?token=abc"},
    "email_verified": {"name": "Ada"},
    "password_reset": {"name": "Ada", "reset_url": "https://app.example/reset-password?token=xyz"},
    "password_changed": {"name": "Ada"},
    "account_deleted": {"name": "Ada"},
}


@pytest.mark.parametrize("template_name,context", list(ALL_TEMPLATES.items()))
def test_render_email_produces_subject_html_and_text(template_name, context):
    subject, html, text = email_service.render_email(template_name, context)
    assert subject and subject.strip()
    assert html and "<html" in html.lower()
    assert text and text.strip()
    # Context values must actually appear in the rendered output.
    for value in context.values():
        assert value in html
        assert value in text


def test_render_email_rejects_unknown_template():
    with pytest.raises(ValueError):
        email_service.render_email("does_not_exist", {})


def test_queue_email_dispatches_to_processing_queue(monkeypatch):
    calls = []

    def fake_dispatch(task, *, args, queue):
        calls.append((task, args, queue))
        return "task-id"

    monkeypatch.setattr("app.services.task_dispatch.dispatch_task", fake_dispatch)

    email_service.queue_email("u@example.com", "welcome_verify", {"name": "Ada", "verify_url": "https://x"})

    assert len(calls) == 1
    task, args, queue = calls[0]
    assert queue == "processing"
    assert args == ("u@example.com", "welcome_verify", {"name": "Ada", "verify_url": "https://x"})
    assert task.name == "workers.tasks.notifications.send_email"


def test_queue_email_swallows_broker_unavailable(monkeypatch):
    from app.services.task_dispatch import BrokerUnavailable

    def boom(task, *, args, queue):
        raise BrokerUnavailable("broker down")

    monkeypatch.setattr("app.services.task_dispatch.dispatch_task", boom)

    # Must not raise — a failed notification enqueue can't break register/reset.
    email_service.queue_email("u@example.com", "password_changed", {"name": "Ada"})


def test_deliver_smtp_console_branch_prints_and_makes_no_network_call(monkeypatch, capsys):
    monkeypatch.setattr(email_service.settings, "smtp_console", True)
    subject, html, text = email_service.render_email("account_deleted", {"name": "Ada"})

    email_service._deliver_smtp("u@example.com", subject, html, text)

    out = capsys.readouterr().out
    assert "u@example.com" in out
    assert subject in out


def test_send_email_task_console_path_runs(monkeypatch):
    """The Celery task body renders + delivers via the console branch cleanly."""
    monkeypatch.setattr(email_service.settings, "smtp_console", True)
    from workers.tasks.notifications import send_email

    # Eager apply runs the task body synchronously in-process (no broker).
    result = send_email.apply(args=("u@example.com", "email_verified", {"name": "Ada"}))
    assert result.successful()
