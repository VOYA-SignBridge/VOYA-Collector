import json


def test_activity_facade_exports_security_components():
    from app import activity
    from app.modules.security import account_controls, activity_monitor, audit_log, geo, ip_controls

    assert activity.block_ip is ip_controls.block_ip
    assert activity.get_block is ip_controls.get_block
    assert activity.list_blocked is ip_controls.list_blocked
    assert activity.log_security_event is audit_log.log_security_event
    assert activity.list_security_log is audit_log.list_security_log
    assert activity.force_logout_user is account_controls.force_logout_user
    assert activity.get_force_logout is account_controls.get_force_logout
    assert activity.is_user_denied is account_controls.is_user_denied
    assert activity.lock_user is account_controls.lock_user
    assert activity.get_user_warning is account_controls.get_user_warning
    assert activity._fmt_until is account_controls.format_until
    assert activity._resolve_usernames is account_controls.resolve_usernames
    assert activity.geo_lookup is geo.geo_lookup
    assert activity._get_geo_reader is geo.get_geo_reader
    assert activity._loc_str is geo.location_label
    assert activity.guard is activity_monitor.guard
    assert activity.record_presence is activity_monitor.record_presence
    assert activity.activity_report is activity_monitor.activity_report


def test_security_controls_fail_open_without_redis(monkeypatch):
    from app.modules.security import account_controls, audit_log, ip_controls

    monkeypatch.setattr(ip_controls, "get_activity_client", lambda: None)
    monkeypatch.setattr(audit_log, "get_activity_client", lambda: None)
    monkeypatch.setattr(account_controls, "get_activity_client", lambda: None)

    assert ip_controls.get_block("203.0.113.1") is None
    assert ip_controls.block_ip("203.0.113.1") is False
    assert ip_controls.list_blocked() == []
    assert audit_log.log_security_event("test") is None
    assert audit_log.list_security_log() == []
    assert account_controls.get_force_logout("user-1") is None
    assert account_controls.get_user_lock("user-1") is None
    assert account_controls.warn_user("user-1", message="notice") is False


def test_timed_ip_block_preserves_payload_and_ttl(monkeypatch):
    from app.modules.security import ip_controls

    calls = []

    class FakeRedis:
        def set(self, key, value, **kwargs):
            calls.append((key, json.loads(value), kwargs))

    monkeypatch.setattr(ip_controls, "get_activity_client", lambda: FakeRedis())
    monkeypatch.setattr(ip_controls.time, "time", lambda: 1000.0)

    assert ip_controls.block_ip(
        "203.0.113.5",
        by="admin",
        reason="rate abuse",
        duration_seconds=60,
    ) is True
    key, payload, options = calls[0]
    assert key == "block:ip:203.0.113.5"
    assert payload == {
        "by": "admin",
        "at": 1000.0,
        "reason": "rate abuse",
        "until": 1060.0,
    }
    assert options == {"ex": 60}


def test_force_logout_preserves_marker_and_refresh_revocation(monkeypatch):
    from app.modules.security import account_controls

    markers = []
    revoked = []

    class FakeRedis:
        def set(self, key, value, **kwargs):
            markers.append((key, json.loads(value), kwargs))

    monkeypatch.setattr(account_controls, "get_activity_client", lambda: FakeRedis())
    monkeypatch.setattr(account_controls, "revoke_all_refresh_tokens", revoked.append)
    monkeypatch.setattr(account_controls.time, "time", lambda: 2000.0)

    assert account_controls.force_logout_user("user-7", by="root", reason="security") is True
    assert revoked == ["user-7"]
    assert markers[0][0] == "forcelogout:user-7"
    assert markers[0][1] == {"ts": 2000.0, "by": "root", "reason": "security"}
    assert markers[0][2]["ex"] > 0


def test_geo_private_address_short_circuits_external_dependencies(monkeypatch):
    from app.modules.security import geo

    def unexpected_client():
        raise AssertionError("private addresses must not touch Redis")

    monkeypatch.setattr(geo, "get_activity_client", unexpected_client)

    assert geo.geo_lookup("127.0.0.1") == {"local": True}
    assert geo.geo_lookup("not-an-ip") == {"local": True}
    assert geo.location_label({"local": True}) == "Nội bộ / LAN"


def test_activity_monitor_filters_health_and_invalid_presence(monkeypatch):
    from app.modules.security import activity_monitor

    class FakeRedis:
        def pipeline(self):
            raise AssertionError("invalid coordinates must not open a pipeline")

    monkeypatch.setattr(activity_monitor, "get_activity_client", lambda: FakeRedis())

    assert activity_monitor.should_record("/health") is False
    assert activity_monitor.should_record("/api/v1/health/ready") is False
    assert activity_monitor.should_record("/api/v1/users/me") is True
    assert activity_monitor.record_presence("127.0.0.1", "invalid", 106.0, None) is None
