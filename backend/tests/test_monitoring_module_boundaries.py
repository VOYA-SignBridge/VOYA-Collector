def test_monitoring_facade_exports_component_callables():
    from app import monitoring
    from app.modules.monitoring import compose_config, gpu, service, snapshots

    assert monitoring.start_gpu_monitor is gpu.start_gpu_monitor
    assert monitoring.collect_resources is service.collect_resources
    assert monitoring.host_snapshot is snapshots.host_snapshot
    assert monitoring.resource_config is compose_config.resource_config


def test_collect_resources_aggregates_snapshots(monkeypatch):
    from app.modules.monitoring import service

    monkeypatch.setattr(service, "host_snapshot", lambda: {"cpu_pct": 10, "ram_pct": 20})
    monkeypatch.setattr(service, "read_gpu_snapshot", lambda: {"available": False})
    monkeypatch.setattr(service, "training_snapshot", lambda: {"active": False})
    monkeypatch.setattr(service, "redis_snapshot", lambda: {"available": True, "used_pct": 5})
    monkeypatch.setattr(service, "disk_snapshot", lambda: {"available": True, "used_pct": 10})
    monkeypatch.setattr(service, "resource_config", lambda: {"available": True})
    report = service.collect_resources()
    assert set(report) == {"timestamp", "host", "gpu", "training", "redis", "disk", "config", "alerts"}
    assert report["host"]["cpu_pct"] == 10
    assert report["config"] == {"available": True}
    assert report["alerts"] == []


def test_alert_rules_remain_independent_from_resource_collection():
    from app.modules.monitoring.service import _build_alerts

    alerts = _build_alerts(
        {"cpu_pct": 95, "ram_pct": 91},
        {"available": True, "vram_pct": 92, "processes": [{"vram_mb": 500}]},
        {"active": False}, {"available": True, "used_pct": 91},
        {"available": True, "used_pct": 96},
    )
    assert [alert["level"] for alert in alerts] == ["critical", "warning", "critical", "warning", "warning", "critical"]
    assert any("KHÔNG có job training" in alert["message"] for alert in alerts)


def test_compose_value_parsers_preserve_supported_formats():
    from app.modules.monitoring.compose_config import _parse_concurrency, _parse_mem_limit

    assert _parse_mem_limit("2g") == 2048.0
    assert _parse_mem_limit("3500m") == 3500.0
    assert _parse_mem_limit(None) == 0.0
    assert _parse_concurrency("celery -A app.worker worker -c 3") == 3
    assert _parse_concurrency(["celery", "worker", "-c4"]) == 4
    assert _parse_concurrency(None) is None


def test_redis_snapshot_reuses_shared_client(monkeypatch):
    from app.modules.monitoring import snapshots

    class FakeRedis:
        def info(self, section):
            assert section == "memory"
            return {"used_memory": 250_000, "maxmemory": 1_000_000}

    monkeypatch.setattr(snapshots, "get_redis_client", lambda: FakeRedis())
    assert snapshots.redis_snapshot() == {
        "available": True, "used_mb": 0.2, "maxmemory_mb": 1.0, "used_pct": 25.0,
    }
