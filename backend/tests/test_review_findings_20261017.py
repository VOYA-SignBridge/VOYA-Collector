"""Chín phát hiện của lượt rà soát mã 17/10/2026, mỗi cái một chốt chặn.

Không cần DB: mọi ca thay đúng hàm truy vấn ở ranh giới và kiểm THAM SỐ / quyết
định mà mã gửi xuống — tức chính chỗ đã sai.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------- 1. phương ngữ

def test_dialect_rename_and_retire_use_the_callers_tenant(monkeypatch):
    from app.routers import vocabulary as voc

    calls = []
    monkeypatch.setattr(voc, "require_tenant", lambda: "truong-b")
    monkeypatch.setattr(voc, "_require_registry_editor",
                        lambda user, tenant_id: calls.append(("auth", tenant_id)))
    monkeypatch.setattr(voc.vr, "rename_dialect",
                        lambda d, n, tenant_id: calls.append(("rename", tenant_id)))
    monkeypatch.setattr(voc.vr, "set_dialect_active",
                        lambda d, a, tenant_id: calls.append(("active", tenant_id)))
    voc.update_dialect("gdcbst", {"display_name": "X", "is_active": False}, {"id": "u"})
    assert calls == [("auth", "truong-b"), ("rename", "truong-b"), ("active", "truong-b")]


# ---------------------------------------------------- 2. admin/editor của tenant

@pytest.mark.parametrize("user,role,expected", [
    ({"id": "u", "is_admin": True}, None, True),
    ({"id": "u"}, "admin", True),
    ({"id": "u"}, "editor", True),
    ({"id": "u"}, None, False),
    ({}, "admin", False),
])
def test_who_manages_tenant_samples(monkeypatch, user, role, expected):
    from app import sample_access, vocabulary_registry

    monkeypatch.setattr(vocabulary_registry, "tenant_role", lambda t, u: role)
    assert sample_access.can_manage_tenant_samples(user, "truong-b") is expected


def test_role_lookup_failure_means_regular_member(monkeypatch):
    from app import sample_access, vocabulary_registry

    def boom(t, u):
        raise RuntimeError("db down")

    monkeypatch.setattr(vocabulary_registry, "tenant_role", boom)
    assert sample_access.can_manage_tenant_samples({"id": "u"}, "t") is False


@pytest.mark.parametrize("manager", [True, False])
def test_read_gate_passes_manage_all_to_the_query(monkeypatch, manager):
    from app import sample_access
    from app.storage import metadata_db

    seen = {}
    monkeypatch.setattr(sample_access, "can_manage_tenant_samples", lambda u, t: manager)

    def fake_fetch(sql, params):
        seen["sql"], seen["params"] = sql, params
        return []

    monkeypatch.setattr(metadata_db, "_fetch_all", fake_fetch)
    sample_access.readable_sample_uids({"id": "u"}, ["s1"], "t")
    assert "(%s OR s.auth_user_id = %s" in seen["sql"]
    assert seen["params"][3] is manager


def test_capture_session_editor_reads_the_tenant_role_not_a_user_field(monkeypatch):
    """`tenant_role` không có trên current_user ngoài /auth/me — bản cũ luôn False."""
    from app import vocabulary_registry
    from app.routers import capture_sessions

    monkeypatch.setattr(vocabulary_registry, "tenant_role",
                        lambda t, u: "editor" if t == "a" else None)
    assert capture_sessions._is_editor({"id": "u"}, "a") is True
    assert capture_sessions._is_editor({"id": "u"}, "b") is False


def test_tenant_manager_may_export_a_tenant_full_of_private_data(monkeypatch):
    from app import sample_access, tenant_lifecycle
    from app.storage import metadata_db

    asked = []

    def fake_fetch(sql, params):
        asked.append(sql)
        return [{"is_admin": False}] if "FROM users" in sql else [{"x": 1}]

    viewer = "11111111-1111-1111-1111-111111111111"
    monkeypatch.setattr(metadata_db, "_fetch_all", fake_fetch)
    monkeypatch.setattr(sample_access, "can_manage_tenant_samples", lambda u, t: True)
    tenant_lifecycle._check_export_privacy("default", viewer)
    assert not any("visibility = 'private'" in q for q in asked)

    monkeypatch.setattr(sample_access, "can_manage_tenant_samples", lambda u, t: False)
    with pytest.raises(tenant_lifecycle.LifecycleError):
        tenant_lifecycle._check_export_privacy("default", viewer)


# ------------------------------------------------ 3. nhãn từ thành viên, duyệt

def test_private_session_cannot_be_decided_even_by_its_owner(monkeypatch):
    from app import moderation_admin
    from app.storage import metadata_db

    monkeypatch.setattr(metadata_db, "_fetch_all",
                        lambda sql, params: [{"auth_user_id": "me", "visibility": "private"}])
    with pytest.raises(moderation_admin.ModerationError) as err:
        moderation_admin.decide_session("cs-1", approve=True, actor_id="me", tenant_id="t")
    assert err.value.status_code == 404


@pytest.mark.parametrize("manager,expected_common", [(False, False), (True, True)])
def test_member_label_request_cannot_set_common_language_and_is_audited(
        monkeypatch, manager, expected_common):
    from types import SimpleNamespace

    from app import sample_access
    from app.routers import classes

    got, audited = {}, []
    meta = SimpleNamespace(class_uid="new-1", class_idx=1, slug="xin-chao", label_original="Xin chao",
                           language="vn", dialect="nam", region="nam", tenant_id="t")
    monkeypatch.setattr(classes, "require_tenant", lambda: "t")
    monkeypatch.setattr(classes, "normalize_dialect", lambda d, tenant_id=None: "nam")
    monkeypatch.setattr(classes, "validate_dialect", lambda d: d)
    monkeypatch.setattr(classes, "list_classes", lambda tenant_id=None: [])
    monkeypatch.setattr(sample_access, "can_manage_tenant_samples", lambda u, t: manager)
    monkeypatch.setattr(classes, "get_or_register_class", lambda **kw: got.update(kw) or meta)
    monkeypatch.setattr(classes, "emit", lambda *a, **k: 0)
    monkeypatch.setattr(classes.audit, "record", lambda action, **kw: audited.append(action))
    classes.request_class(None, {"label": "Xin chao", "dialect": "nam", "is_common_language": True},
                          {"id": "u"})
    assert got["is_common_language"] is expected_common
    assert audited == ["data.class.request"]


# ------------------------------------------------- 4. xử lý lại video theo tenant

def test_reprocess_only_accepts_rows_of_the_request_tenant():
    from app.routers.upload import _in_request_tenant

    assert _in_request_tenant({"tenant_id": "a"}, "a") is True
    assert _in_request_tenant({"tenant_id": "b"}, "a") is False
    assert _in_request_tenant({"tenant_id": ""}, "default") is True


# ------------------------------------------------------------------- 9. Learn

def test_learn_page_attaches_own_data_only_to_the_page(monkeypatch):
    from app.routers import learn

    words = [{"slug": f"w{i}", "kind": "tu_thuong", "pos": "", "variants": []} for i in range(100)]
    attached = []
    monkeypatch.setattr(learn.learn_catalog, "filter_words", lambda *a: words)
    monkeypatch.setattr(learn, "_own_classes_by_slug", lambda: {})
    monkeypatch.setattr(learn, "_attach_own",
                        lambda w, own: attached.append(w) or {**w, "own_sample_count": 0})
    out = learn.list_signs(q="", region="", kind="", pos="", letter="", has_own=False,
                           page=2, limit=24)
    assert len(out["items"]) == 24 and len(attached) == 24
    assert out["total"] == 100 and out["pages"] == 5
