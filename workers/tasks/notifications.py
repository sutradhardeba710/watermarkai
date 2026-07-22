"""Notification Celery tasks — transactional email delivery.

Runs on the ``processing`` queue (reusing the combined worker's existing queues
so no worker command/compose change is needed). The API never sends mail
inline: it calls ``app.services.email_service.queue_email`` which dispatches
``send_email`` here, so SMTP latency/failures stay off the request path.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger("workers.notifications")


@shared_task(name="workers.tasks.notifications.send_email", bind=True, max_retries=3, queue="processing")
def send_email(self, to: str, template_name: str, context: dict) -> None:
    """Render and deliver one email. Retries on transient SMTP failures."""
    from app.services import email_service

    try:
        subject, html, text = email_service.render_email(template_name, context)
        email_service._deliver_smtp(to, subject, html, text)
    except ValueError:
        # Unknown template — a programming error, not transient. Don't retry.
        logger.exception("send_email got an unknown template %r; dropping", template_name)
        return
    except Exception as exc:  # noqa: BLE001 — SMTP/network errors are retryable
        logger.warning("send_email to %s (%s) failed: %s; retrying", to, template_name, exc)
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
