"""Celery task dispatch with resilient publishing (shared by API routes).

Why this exists
---------------
The API process imports the Celery app to `apply_async` jobs but is a long-lived
process. On Windows — especially with the project living in a OneDrive folder —
the pooled broker (Redis) connection can go stale between requests, so the *first*
publish after an idle period raises a kombu ``OperationalError`` ("connection
refused"/"broken pipe") even though Redis is perfectly healthy. A fresh
connection then succeeds immediately.

Previously both /process and /analyze wrapped the publish in a bare
``except Exception`` that (a) logged nothing, making the failure impossible to
diagnose, and (b) mapped *every* error — including a one-off stale connection —
straight to a user-facing "queue is not available" 503 plus a credit refund.

`dispatch_task` fixes that:
  * retries the publish once on a brand-new connection when the first attempt
    fails with a connection-level error (handles the stale-socket case), and
  * logs the real exception with a traceback so genuine failures are visible.

It raises `BrokerUnavailable` only when the broker is truly unreachable; any
other exception (e.g. a programming/import error) propagates unchanged so it is
surfaced as a real 500 with a stack trace instead of being masked.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("app.task_dispatch")


class BrokerUnavailable(RuntimeError):
    """Raised when a task genuinely could not be published to the broker."""


# kombu/redis raise a small family of errors when the broker is unreachable or
# the pooled socket has gone stale. We treat these — and only these — as
# retryable/BrokerUnavailable; anything else is a real bug and must propagate.
def _is_connection_error(exc: BaseException) -> bool:
    try:
        from kombu.exceptions import OperationalError as KombuOperationalError
    except Exception:  # pragma: no cover - kombu always present with celery
        KombuOperationalError = ()  # type: ignore[assignment]

    if isinstance(exc, KombuOperationalError):
        return True
    # redis-py connection failures (in case they surface undecorated) and the
    # stdlib socket/OS errors that back them.
    name = exc.__class__.__name__
    if name in {"ConnectionError", "TimeoutError", "BusyLoadingError"}:
        return True
    return isinstance(exc, (ConnectionError, OSError))


_RETRY_POLICY = {"max_retries": 2, "interval_start": 0, "interval_step": 0.5, "interval_max": 1}


def dispatch_task(task, *, args: tuple, queue: str) -> str:
    """Publish `task` to `queue`, retrying once on a fresh connection.

    Returns the Celery task id on success. Raises `BrokerUnavailable` if the
    broker is genuinely unreachable; re-raises any non-connection error as-is.
    """
    # Ensure our Celery app is the current app so the @shared_task binds to it
    # (broker_url, queues, pool settings). See workers/celery_app.py.
    import workers.celery_app  # noqa: F401
    from workers.celery_app import celery_app

    try:
        result = task.apply_async(args=args, queue=queue, retry=True, retry_policy=_RETRY_POLICY)
        return result.id
    except Exception as first_exc:  # noqa: BLE001 — inspected below
        if not _is_connection_error(first_exc):
            # Not a broker problem (import error, serialization bug, etc.) — this
            # is a real defect. Log it and let it bubble up as a 500.
            logger.exception("Task publish to queue %r failed with a non-broker error", queue)
            raise

        # Stale pooled connection is the common Windows/OneDrive case: open a
        # brand-new connection and try one more time before giving up.
        logger.warning(
            "Broker publish to %r failed (%s); retrying once on a fresh connection",
            queue, first_exc.__class__.__name__,
        )
        try:
            with celery_app.connection_for_write() as fresh_conn:
                result = task.apply_async(
                    args=args, queue=queue, connection=fresh_conn,
                    retry=True, retry_policy=_RETRY_POLICY,
                )
            logger.info("Broker publish to %r succeeded on fresh-connection retry", queue)
            return result.id
        except Exception as retry_exc:  # noqa: BLE001
            logger.exception("Broker publish to %r failed after fresh-connection retry", queue)
            raise BrokerUnavailable(str(retry_exc)) from retry_exc
