"""Mọi chỗ chọn dữ liệu hoặc xét vai theo tổ chức ĐANG LÀM VIỆC, không theo tổ chức nhà.

Rà 18/10/2026 sau sự cố huấn luyện (xem test_training_working_tenant.py): cùng một
lỗi — đọc `users.tenant_id` (nhà) trong khi lệnh ghi đi vào phạm vi request (tổ
chức đang làm việc, `users.active_tenant_id` sau khi kiểm tư cách thành viên) —
nằm ở nhiều chỗ khác, và ở hai cổng quyền thì nó thành LEO QUYỀN:

  * biên tập viên ở trường B, làm việc ở VOYA với vai thành viên thường, sửa
    được danh mục của VOYA (`require_tenant_editor` xét vai ở B);
  * biên tập viên thật của VOYA có nhà ở nơi khác thì bị chặn oan.

Khoá API là ngoại lệ có chủ đích: nó thuộc đúng một tổ chức, không có khái niệm
"đang làm việc". Middleware từng không hiểu khoá (`voya_...` không phải JWT) nên
mọi lượt gọi bằng khoá rơi về phạm vi công khai `default` — khoá của trường B
đọc/ghi qua phạm vi request là chạm dữ liệu VOYA.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.modules.saas.tenant_middleware as tm
import app.modules.dataset.vocabulary_registry as vr
from app.auth import get_current_user, require_tenant_editor
from app.main import app
from app.modules.saas.tenant_context import tenant_scope

HOME = "truong-b"
WORKING = "default"
USER = {"id": "8744d8f3-0000-4000-8000-000000000000", "username": "Minh67",
        "is_admin": False, "tenant_id": HOME}

client = TestClient(app)


@pytest.fixture
def working_in_voya(monkeypatch):
    import app.modules.security.access_gate as gate

    monkeypatch.setattr(tm, "resolve_tenant", lambda cookie, bearer: WORKING)
    # Người dùng giả không có grant trong DB; cổng truy cập không phải thứ đang kiểm.
    monkeypatch.setattr(gate, "_has_any_tenant_grant", lambda user: True)
    app.dependency_overrides[get_current_user] = lambda: dict(USER)
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _editor_only_in(tenant):
    """`can_edit_registry` giả: chỉ là biên tập viên ở đúng một tổ chức."""
    seen = []

    def _can(tenant_id, user_id, is_admin):
        seen.append(tenant_id)
        return tenant_id == tenant
    return _can, seen


# ------------------------------------------------------------ cổng biên tập


class TestTenantEditorGate:
    def test_role_is_read_in_the_working_tenant(self, monkeypatch):
        can, seen = _editor_only_in(WORKING)
        monkeypatch.setattr(vr, "can_edit_registry", can)
        with tenant_scope(WORKING):
            assert require_tenant_editor(current_user=dict(USER))["username"] == "Minh67"
        assert seen == [WORKING]

    def test_editor_at_home_only_cannot_edit_the_working_tenant(self, monkeypatch):
        """Chiều leo quyền: vai ở trường B không mở được danh mục của VOYA."""
        can, _ = _editor_only_in(HOME)
        monkeypatch.setattr(vr, "can_edit_registry", can)
        with tenant_scope(WORKING), pytest.raises(HTTPException) as exc:
            require_tenant_editor(current_user=dict(USER))
        assert exc.value.status_code == 403

    def test_api_key_keeps_its_own_scope_rule(self, monkeypatch):
        monkeypatch.setattr(vr, "can_edit_registry",
                            lambda *a: pytest.fail("khoá API không tra tenant_members"))
        key_user = {"id": "apikey:k1", "auth_method": "api_key", "api_key_can_write": True,
                    "tenant_id": HOME, "is_admin": False}
        with tenant_scope(HOME):
            assert require_tenant_editor(current_user=key_user) is key_user


# ------------------------------------------------------------ khoá API ở middleware


class TestApiKeyRequestScope:
    def test_a_key_scopes_the_request_to_the_keys_tenant(self, monkeypatch):
        import app.modules.security.api_keys as api_keys

        monkeypatch.setattr(api_keys, "authenticate",
                            lambda raw: {"tenant_id": "iso_b"} if raw == "voya_abc_secret" else None)
        assert tm.resolve_tenant(None, "voya_abc_secret") == "iso_b"

    def test_a_session_cookie_still_wins_over_a_key(self, monkeypatch):
        """Cùng thứ tự với `get_current_user_optional`: có cookie thì người đang
        ngồi trước trình duyệt là danh tính, không phải khoá dán vào curl."""
        import app.modules.security.api_keys as api_keys
        import app.auth as auth

        monkeypatch.setattr(api_keys, "authenticate", lambda raw: {"tenant_id": "iso_b"})
        monkeypatch.setattr(auth, "_subject_of", lambda token: "u-1" if token == "cookie-jwt" else None)
        monkeypatch.setattr(tm, "_tenant_of_user", lambda uid: "truong-c")
        assert tm.resolve_tenant("cookie-jwt", "voya_abc_secret") == "truong-c"


# ------------------------------------------------------------ webhook sự kiện lớp


def test_class_created_event_goes_to_the_class_tenant(working_in_voya, monkeypatch):
    """Sự kiện về một lớp của VOYA không được gửi tới webhook của trường B."""
    import app.routers.classes as classes

    can, _ = _editor_only_in(WORKING)
    monkeypatch.setattr(vr, "can_edit_registry", can)
    monkeypatch.setattr(classes, "normalize_dialect", lambda d, tenant_id=None: d)
    monkeypatch.setattr(classes, "validate_dialect", lambda d: d)
    meta = SimpleNamespace(class_uid="c-1", class_idx=1, slug="tom", label_original="tôm",
                           language="vn", dialect="hoa-de", region="nam", tenant_id=WORKING)
    monkeypatch.setattr(classes, "get_or_register_class", lambda **kw: meta)
    sent = []
    monkeypatch.setattr(classes, "emit", lambda tenant, event, data: sent.append((tenant, event)))

    r = client.post("/classes/register", json={"label": "tôm", "dialect": "hoa-de"})
    assert r.status_code == 200, r.text
    assert sent == [(WORKING, "class.created")]


# ------------------------------------------------------------ integrations / billing / workspace


def test_integrations_manage_the_working_tenants_keys(working_in_voya, monkeypatch):
    import app.routers.integrations as integ

    can, _ = _editor_only_in(WORKING)
    monkeypatch.setattr(vr, "can_edit_registry", can)
    seen = []
    monkeypatch.setattr(integ.api_keys_service, "list_keys",
                        lambda tenant_id, include_revoked=False: seen.append(tenant_id) or [])
    monkeypatch.setattr(integ.webhooks_service, "list_endpoints",
                        lambda tenant_id: seen.append(tenant_id) or [])
    assert client.get("/integrations/api-keys").status_code == 200
    assert client.get("/integrations/webhooks").status_code == 200
    assert seen == [WORKING, WORKING]


def test_billing_usage_is_the_working_tenants(working_in_voya, monkeypatch):
    import app.routers.billing as billing

    seen = []
    monkeypatch.setattr(billing.usage, "usage_totals", lambda t, days=30: seen.append(t) or {})
    monkeypatch.setattr(billing.usage, "usage_series", lambda t, days=30: seen.append(t) or [])
    r = client.get("/billing/usage")
    assert r.status_code == 200, r.text
    assert r.json()["tenant_id"] == WORKING and seen == [WORKING, WORKING]


def test_workspace_tree_is_the_working_tenants(working_in_voya, monkeypatch):
    import app.routers.workspaces as ws

    seen = []
    monkeypatch.setattr(ws.workspace_admin, "scope_tree_summary", lambda t: seen.append(t) or {})
    r = client.get("/workspaces/summary")
    assert r.status_code == 200, r.text
    assert seen == [WORKING]


def test_workspace_admin_role_is_read_in_the_working_tenant(working_in_voya, monkeypatch):
    """Cổng thứ hai cùng kiểu: quản trị ở trường B không sửa được cây phạm vi của VOYA."""
    import app.routers.workspaces as ws

    seen = []
    monkeypatch.setattr(vr, "tenant_role", lambda t, uid: seen.append(t) or ("admin" if t == HOME else "member"))
    with pytest.raises(HTTPException) as exc:
        with tenant_scope(WORKING):
            ws.require_tenant_admin(user=dict(USER))
    assert exc.value.status_code == 403 and seen == [WORKING]
