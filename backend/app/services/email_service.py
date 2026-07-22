"""Transactional email: template rendering, async dispatch, and SMTP delivery.

Templates live in ``app/templates/email/`` as Jinja2 ``.html.jinja`` /
``.txt.jinja`` pairs (multipart/alternative — better inbox/spam handling than
HTML-only). Sending is always asynchronous: API routes call ``queue_email``,
which hands off to the Celery task in ``workers/tasks/notifications.py`` so a
slow/unreachable SMTP server never blocks a request. ``_deliver_smtp`` (the
actual network call) is only ever invoked from the worker process.
"""
from __future__ import annotations

import logging
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import get_settings

logger = logging.getLogger("app.email")

settings = get_settings()

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(enabled_extensions=("html.jinja",)),
)

# Subjects live here rather than in a Jinja block — one less template concept.
_SUBJECTS = {
    "welcome_verify": "Welcome to ClearFrame — verify your email",
    "email_verified": "Your email is verified",
    "password_reset": "Reset your ClearFrame password",
    "password_changed": "Your ClearFrame password was changed",
    "account_deleted": "Your ClearFrame account was deleted",
}


def render_email(template_name: str, context: dict) -> tuple[str, str, str]:
    """Render ``(subject, html_body, text_body)`` for a named template."""
    if template_name not in _SUBJECTS:
        raise ValueError(f"Unknown email template: {template_name!r}")
    subject = _SUBJECTS[template_name]
    html = _env.get_template(f"{template_name}.html.jinja").render(subject=subject, **context)
    text = _env.get_template(f"{template_name}.txt.jinja").render(subject=subject, **context)
    return subject, html, text


def queue_email(to: str, template_name: str, context: dict) -> None:
    """Enqueue an email send. Never raises — a notification that fails to
    enqueue must not turn a successful register/reset/etc. into a 500."""
    from app.services.task_dispatch import BrokerUnavailable, dispatch_task

    try:
        from workers.tasks.notifications import send_email as send_email_task

        dispatch_task(send_email_task, args=(to, template_name, context), queue="processing")
    except BrokerUnavailable:
        logger.error("Could not enqueue %r email to %s: broker unavailable", template_name, to)
    except Exception:  # noqa: BLE001 — a notification failure must never break the caller
        logger.exception("Could not enqueue %r email to %s", template_name, to)


def _deliver_smtp(to: str, subject: str, html: str, text: str) -> None:
    """Send one email. Called only from the Celery worker task."""
    if settings.smtp_console:
        # Dev default: no SMTP configured, just make the content visible.
        print(f"[email] to={to} subject={subject}\n{text}\n", flush=True)
        return

    import smtplib

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


__all__ = ["render_email", "queue_email", "_deliver_smtp"]
