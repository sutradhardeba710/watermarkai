from __future__ import annotations

from app.services import admin_service, health_monitor, request_metrics


def test_collect_populates_every_service_and_metric(monkeypatch):
    monkeypatch.setattr(
        health_monitor,
        "_database_snapshot",
        lambda _db: (
            {"ok": True, "detail": "database", "latency_ms": 1.0},
            {"db_latency_ms": 1.0, "db_connections": 10.0},
        ),
    )
    monkeypatch.setattr(
        health_monitor,
        "_redis_snapshot",
        lambda: (
            {"ok": True, "detail": "redis", "latency_ms": 1.0, "memory_mb": 4.0},
            object(),
            {"worker@test": 1},
        ),
    )
    monkeypatch.setattr(
        health_monitor,
        "_cached_probe",
        lambda name, _probe: {"ok": True, "detail": name, "latency_ms": 1.0},
    )
    monkeypatch.setattr(
        health_monitor,
        "_run_probe",
        lambda _probe: {"ok": True, "detail": "signed", "latency_ms": 0.1},
    )
    monkeypatch.setattr(health_monitor, "_webhook_failures", lambda _db: 0)
    monkeypatch.setattr(
        request_metrics,
        "snapshot",
        lambda _client: {"api_response_ms": 12.0, "api_error_rate": 0.0},
    )

    checks, metrics = health_monitor.collect(
        object(),
        {"queue_depth": 0, "worker_heartbeat_failures": 0},
    )

    assert set(checks) == set(admin_service.SERVICE_NAMES)
    assert all(row["ok"] is True for row in checks.values())
    rows = admin_service.evaluate_health_metrics(metrics)
    assert all(row["value"] is not None for row in rows)
    assert all(row["status"] == "ok" for row in rows)


class _Pipeline:
    def __init__(self, rows):
        self.rows = rows

    def hgetall(self, _key):
        return self

    def execute(self):
        return self.rows


class _Redis:
    def __init__(self, rows):
        self.rows = rows

    def pipeline(self, transaction=False):
        assert transaction is False
        return _Pipeline(self.rows)


def test_request_metrics_snapshot_aggregates_window():
    rows = [
        {b"requests": b"3", b"errors": b"1", b"latency_ms": b"90"},
        {b"requests": b"1", b"latency_ms": b"10"},
        {},
        {},
        {},
    ]

    result = request_metrics.snapshot(_Redis(rows))

    assert result == {"api_response_ms": 25.0, "api_error_rate": 25.0}
