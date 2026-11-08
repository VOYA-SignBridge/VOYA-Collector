"""Vai tổ chức làm được việc của tổ chức, nhưng không với sang tổ chức khác.

Trước 05/11/2026 promote mô hình và sửa/xoá lớp gác bằng `require_admin`, tức là
chỉ người vận hành nền tảng làm được, trái với `authorization/catalog.py`:
`training.promote`, `class.update`, `class.delete` thuộc vai tổ chức. Các bài ở
đây chốt cả hai chiều của lần mở quyền đó:

  * vai đúng thì qua; thành viên thường và khoá API thì không
  * mở quyền KHÔNG mở ranh giới: slot realtime của tổ chức không đè slot của tổ
    chức khác, không hiện và không gọi được từ tổ chức khác, thùng rác chỉ liệt
    kê (và chỉ dọn) đúng tổ chức đang làm việc

Không cần Postgres hay dịch vụ realtime: các ranh giới ngoài là bản giả.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException  # pyright: ignore[reportMissingImports]

from app import auth, catalog_sync, realtime_slots
from app.routers import dataset as dataset_router
from app.routers import realtime_proxy, training
from app.storage import metadata_db
from app.tenant_context import tenant_scope

TENANT_A = "truong-a-111111"
TENANT_B = "truong-b-222222"

EDITOR = {"id": "00000000-0000-0000-0000-00000000000a", "username": "bien_tap",
          "is_admin": False}
MEMBER = {"id": "00000000-0000-0000-0000-00000000000b", "username": "thanh_vien",
          "is_admin": False}
PLATFORM = {"id": "00000000-0000-0000-0000-0000000000ff", "username": "superadmin",
            "is_admin": True}
API_KEY = {"id": "api-key:1", "username": "khoa", "is_admin": False,
           "auth_method": "api_key", "api_key_can_write": True}


# --------------------------------------------------------------------------- slot


def test_slotId_forCommunity_keepsTheBareDialect():
    assert realtime_slots.slot_id("hoa-de", "default") == "hoa-de"
    assert realtime_slots.slot_owner("hoa-de") is None


def test_slotId_forOrganisation_namesItsOwner():
    model_id = realtime_slots.slot_id("hoa-de", TENANT_A)
    assert model_id != "hoa-de"
    assert realtime_slots.slot_owner(model_id) == TENANT_A


@pytest.mark.parametrize("tenant, expected", [
    (TENANT_A, True),
    (TENANT_B, False),
    (None, False),   # khách vãng lai
    ("", False),
])
def test_visibleTo_ownedSlot_onlyItsOwner(tenant, expected):
    assert realtime_slots.visible_to(f"hoa-de@{TENANT_A}", tenant) is expected


@pytest.mark.parametrize("tenant", [TENANT_A, None])
def test_visibleTo_sharedSlot_everyone(tenant):
    assert realtime_slots.visible_to("hoa-de", tenant) is True


# --------------------------------------------------------------------------- registry


def _entry(model_id, dialect="hoa-de", name="Hòa đê"):
    return {"id": model_id, "dialect": dialect, "name": name}


def _promote_into(monkeypatch, tmp_path, models, model_id):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"schema_version": "1", "models": models}), encoding="utf-8")
    monkeypatch.setattr(training, "REGISTRY_PATH", path)
    assert training._update_registry(model_id, "checkpoints/x.pt", "Tên mới", {}, "hoa-de", "vn")
    return {m["id"]: m for m in json.loads(path.read_text(encoding="utf-8"))["models"]}


def test_updateRegistry_organisationPromotion_keepsSharedModel(monkeypatch, tmp_path):
    out = _promote_into(monkeypatch, tmp_path, [_entry("hoa-de")], f"hoa-de@{TENANT_A}")
    assert set(out) == {"hoa-de", f"hoa-de@{TENANT_A}"}
    assert out["hoa-de"].get("checkpoint_path") is None, "slot chung bị ghi đè"


def test_updateRegistry_organisationPromotion_keepsOtherOrganisations(monkeypatch, tmp_path):
    out = _promote_into(monkeypatch, tmp_path, [_entry(f"hoa-de@{TENANT_B}")],
                        f"hoa-de@{TENANT_A}")
    assert f"hoa-de@{TENANT_B}" in out


def test_updateRegistry_sameOwner_replacesPreviousModel(monkeypatch, tmp_path):
    out = _promote_into(monkeypatch, tmp_path, [_entry(f"hoa-de@{TENANT_A}", name="Bản cũ")],
                        f"hoa-de@{TENANT_A}")
    assert list(out) == [f"hoa-de@{TENANT_A}"]
    assert out[f"hoa-de@{TENANT_A}"]["checkpoint_path"] == "checkpoints/x.pt"
    assert out[f"hoa-de@{TENANT_A}"]["name"] == "Bản cũ", "tên hiển thị phải được giữ"


def test_updateRegistry_sharedSlot_replacesOldTrainingEntries(monkeypatch, tmp_path):
    out = _promote_into(monkeypatch, tmp_path, [_entry("training_abc123")], "hoa-de")
    assert list(out) == ["hoa-de"]


def test_updateRegistry_organisationSlot_doesNotInheritSharedName(monkeypatch, tmp_path):
    out = _promote_into(monkeypatch, tmp_path, [_entry("hoa-de", name="Hòa đê")],
                        f"hoa-de@{TENANT_A}")
    assert out[f"hoa-de@{TENANT_A}"]["name"] == "Tên mới"


# --------------------------------------------------------------------------- proxy


class _Upstream:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


class _Client:
    def __init__(self, payload):
        self.payload = payload

    async def get(self, _url):
        return _Upstream(self.payload)


async def _list_as(monkeypatch, tenant):
    monkeypatch.setattr(realtime_proxy, "_get_client", lambda: _Client([
        {"id": "hoa-de"}, {"id": f"hoa-de@{TENANT_A}"}, {"id": f"hoa-de@{TENANT_B}"},
    ]))
    response = SimpleNamespace(headers={})
    if tenant is None:
        return await realtime_proxy.proxy_models(None, response)
    with tenant_scope(tenant):
        return await realtime_proxy.proxy_models(None, response)


def test_proxyModels_organisation_hidesOtherOrganisations(monkeypatch):
    ids = [m["id"] for m in asyncio.run(_list_as(monkeypatch, TENANT_A))]
    assert ids == ["hoa-de", f"hoa-de@{TENANT_A}"]


def test_proxyModels_guest_seesOnlySharedModels(monkeypatch):
    ids = [m["id"] for m in asyncio.run(_list_as(monkeypatch, None))]
    assert ids == ["hoa-de"]


class _PredictRequest:
    def __init__(self, model_id):
        frames = [[0.0] * 126 for _ in range(60)]
        self._raw = json.dumps({"model_id": model_id, "frames": frames}).encode()
        self.headers = {}

    async def body(self):
        return self._raw


def test_proxyPredict_foreignSlot_returns404WithoutCallingUpstream(monkeypatch):
    # Không được chạm tới dịch vụ suy luận: nếu chạm, `_get_semaphore` sẽ ném.
    monkeypatch.setattr(realtime_proxy, "_get_semaphore", lambda: pytest.fail("đã gọi upstream"))
    with tenant_scope(TENANT_B):
        with pytest.raises(HTTPException) as err:
            asyncio.run(realtime_proxy.proxy_predict(
                _PredictRequest(f"hoa-de@{TENANT_A}"), SimpleNamespace(headers={})))
    assert err.value.status_code == 404


# --------------------------------------------------------------------------- cổng quyền


def test_requireTenantCurator_person_passes():
    assert auth.require_tenant_curator(EDITOR) is EDITOR


def test_requireTenantCurator_apiKey_returns403():
    with pytest.raises(HTTPException) as err:
        auth.require_tenant_curator(API_KEY)
    assert err.value.status_code == 403


def _roles(monkeypatch, table):
    """Bảng `(tenant, user_id) -> vai`, thay cho tra `tenant_members`."""
    import app.vocabulary_registry as vr

    monkeypatch.setattr(vr, "tenant_role", lambda t, u: table.get((t, str(u))))


def test_requireTenantEditor_roleElsewhere_returns403(monkeypatch):
    _roles(monkeypatch, {(TENANT_A, EDITOR["id"]): "editor"})
    with tenant_scope(TENANT_A):
        assert auth.require_tenant_editor(EDITOR) is EDITOR
    with tenant_scope(TENANT_B):
        with pytest.raises(HTTPException) as err:
            auth.require_tenant_editor(EDITOR)
    assert err.value.status_code == 403


def test_requireTenantEditor_plainMember_returns403(monkeypatch):
    _roles(monkeypatch, {})
    with tenant_scope(TENANT_A):
        with pytest.raises(HTTPException):
            auth.require_tenant_editor(MEMBER)


@pytest.mark.parametrize("path, method", [
    ("/classes/{class_ref}", "PUT"),
    ("/classes/{class_ref}", "DELETE"),
    ("/classes/trash", "GET"),
    ("/classes/trash/restore", "POST"),
    ("/classes/trash/purge", "POST"),
    ("/classes/{class_uid}/restore", "POST"),
    ("/classes/{class_uid}/purge", "DELETE"),
    ("/dataset/labels/{class_ref}", "PUT"),
    ("/dataset/labels/{class_ref}", "DELETE"),
])
def test_routes_tenantWork_gatedByCuratorNotPlatformAdmin(path, method):
    from app.main import app

    route = next(r for r in app.routes
                 if getattr(r, "path", "").endswith(path) and method in getattr(r, "methods", ()))
    gates = {d.call for d in route.dependant.dependencies}
    assert auth.require_tenant_curator in gates
    assert auth.require_admin not in gates


def test_withCapabilities_workingElsewhere_reportsWorkingTenantRights(monkeypatch):
    """`tenant_role` đọc tổ chức NHÀ; nút trên giao diện phải theo nơi đang làm việc."""
    from app.routers import auth as auth_router

    _roles(monkeypatch, {(TENANT_A, EDITOR["id"]): "editor"})
    nguoi = {**EDITOR, "tenant_id": TENANT_A}
    with tenant_scope(TENANT_A):
        assert auth_router._with_capabilities(nguoi)["can_edit_tenant"] is True
    with tenant_scope(TENANT_B):
        assert auth_router._with_capabilities(nguoi)["can_edit_tenant"] is False


def test_withCapabilitiesAtWork_guestScope_reportsWorkingTenantRights(monkeypatch):
    """`/login` và `/refresh` vào với phạm vi khách mà phải trả lời giống `/me`."""
    from app import tenant_middleware
    from app.routers import auth as auth_router

    _roles(monkeypatch, {(TENANT_A, EDITOR["id"]): "editor"})
    monkeypatch.setattr(tenant_middleware, "_tenant_of_user", lambda _id: TENANT_A)
    with tenant_scope(TENANT_B):
        assert auth_router._with_capabilities(EDITOR)["can_edit_tenant"] is False
        assert auth_router._with_capabilities_at_work(EDITOR)["can_edit_tenant"] is True


def test_withCapabilitiesAtWork_lookupFails_stillAnswers(monkeypatch):
    """Tra nơi làm việc hỏng không được làm ngã đăng nhập."""
    from app import tenant_middleware
    from app.routers import auth as auth_router

    def hong(_id):
        raise RuntimeError("db")

    _roles(monkeypatch, {})
    monkeypatch.setattr(tenant_middleware, "_tenant_of_user", hong)
    with tenant_scope(TENANT_B):
        assert auth_router._with_capabilities_at_work(EDITOR)["can_edit_tenant"] is False


# --------------------------------------------------------------------------- thùng rác


@pytest.fixture
def captured_sql(monkeypatch):
    calls = []

    def _fake(sql, params=()):
        calls.append((" ".join(sql.split()), params))
        return []

    monkeypatch.setattr(metadata_db, "_fetch_all", _fake)
    return calls


def test_listDeletedClasses_withTenant_filtersInTheQuery(captured_sql):
    metadata_db.list_deleted_classes(TENANT_A)
    sql, params = captured_sql[0]
    assert "c.tenant_id = %s" in sql
    assert params == (TENANT_A,)


def test_listDeletedSamples_withTenant_filtersInTheQuery(captured_sql):
    metadata_db.list_deleted_samples(TENANT_A)
    sql, params = captured_sql[0]
    assert "s.tenant_id = %s" in sql
    assert params == (TENANT_A,)


def test_emptyClassTrash_withTenant_purgesOnlyThatTenant(monkeypatch):
    seen = {}

    def _list(tenant_id):
        seen["tenant"] = tenant_id
        return [{"class_uid": "c1"}]

    monkeypatch.setattr(catalog_sync, "list_trash_classes", _list)
    monkeypatch.setattr(catalog_sync, "bulk_purge_classes", lambda uids: {"ok": uids})
    assert catalog_sync.empty_class_trash(TENANT_A) == {"ok": ["c1"]}
    assert seen["tenant"] == TENANT_A


# --------------------------------------------------------------------------- mẫu


def test_checkSampleOwnership_editorOfTenant_allowsUnownedSample(monkeypatch):
    _roles(monkeypatch, {(TENANT_A, EDITOR["id"]): "editor"})
    monkeypatch.setattr(dataset_router, "get_sample_owner", lambda _s: None)
    with tenant_scope(TENANT_A):
        dataset_router._check_sample_ownership("s1", EDITOR)  # không ném


def test_checkSampleOwnership_plainMember_refusesUnownedSample(monkeypatch):
    _roles(monkeypatch, {})
    monkeypatch.setattr(dataset_router, "get_sample_owner", lambda _s: None)
    with tenant_scope(TENANT_A):
        with pytest.raises(HTTPException) as err:
            dataset_router._check_sample_ownership("s1", MEMBER)
    assert err.value.status_code == 403


def test_checkSampleOwnership_editorElsewhere_refuses(monkeypatch):
    _roles(monkeypatch, {(TENANT_A, EDITOR["id"]): "editor"})
    monkeypatch.setattr(dataset_router, "get_sample_owner", lambda _s: "ai-do-khac")
    with tenant_scope(TENANT_B):
        with pytest.raises(HTTPException) as err:
            dataset_router._check_sample_ownership("s1", EDITOR)
    assert err.value.status_code == 403


def test_checkSampleOwnership_platformAdminWithoutScope_allows(monkeypatch):
    monkeypatch.setattr(dataset_router, "get_sample_owner", lambda _s: None)
    dataset_router._check_sample_ownership("s1", PLATFORM)  # không ném


# --------------------------------------------------------------------------- khởi động


def test_initDb_thenFirstCatalogEdit_doesNotRepeatSchemaWork(monkeypatch):
    """Lần sửa nhãn đầu tiên của một worker không được chạy lại DDL trong request."""
    from app import db

    monkeypatch.setattr(catalog_sync, "_SCHEMA_ENSURED", False)
    monkeypatch.setattr(metadata_db, "ensure_tables", lambda: None)
    goi = []
    monkeypatch.setattr(catalog_sync, "_db_ensure_tables", lambda: goi.append(1))
    db._init_db(False)
    catalog_sync.ensure_tables()
    assert goi == []


# --------------------------------------------------------------------------- làm việc ở tổ chức khác


def test_guardStorage_workingElsewhere_reservesAtTheWorkingTenant(monkeypatch):
    """Giữ chỗ ở tổ chức nhà trong phạm vi tổ chức kia từng làm tải lên trả 500."""
    from app import quota_deps, storage_quota

    giu = []
    monkeypatch.setattr(storage_quota, "reserve", lambda tenant, n: giu.append(tenant))
    with tenant_scope(TENANT_B):
        quota_deps.guard_storage({**EDITOR, "tenant_id": TENANT_A}, nbytes=10)
    assert giu == [TENANT_B]


def test_switchTenant_auditRow_isWrittenInsideTheTargetScope(monkeypatch):
    """Dòng mang tenant đích phải ghi trong phạm vi đích, nếu không RLS từ chối."""
    from types import SimpleNamespace as NS

    from app.routers import tenants as tenants_router
    from app.tenant_context import current_tenant

    pham_vi = []
    monkeypatch.setattr(tenants_router.tenant_admin, "set_active_tenant",
                        lambda *_: {"tenant_id": TENANT_B, "is_home": False})
    monkeypatch.setattr(tenants_router.audit, "record", lambda *a, **k: pham_vi.append(current_tenant()))
    ham = next(r.endpoint for r in tenants_router.router.routes if getattr(r, "path", "").endswith("/switch"))
    with tenant_scope(TENANT_A):
        ham(payload=NS(tenant_id=TENANT_B), request=None, current_user=EDITOR)
    assert pham_vi == [TENANT_B]


def test_processVideoJob_classAtCap_returnsAReasonTheUiCanShow(monkeypatch, tmp_path):
    """Không có `message`, giao diện báo "không nhận diện được bàn tay" cho lớp đã đầy."""
    from app.processing import pipeline

    monkeypatch.setattr(pipeline.settings, "max_samples_per_class", 200, raising=False)
    monkeypatch.setattr(pipeline, "get_or_register_class", lambda **_k: SimpleNamespace(class_uid="c1"))
    monkeypatch.setattr(pipeline, "count_samples_for_class", lambda _uid: 228)
    ket_qua = pipeline.process_video_job(video_path=str(tmp_path / "video.mp4"), user="u", user_id="u", label="rang muoi",
                                         session_id="s", dialect="hoa-de", language="vn")
    assert ket_qua["status"] == "skipped_cap"
    assert "đã đủ 200 mẫu" in ket_qua["message"]


# --------------------------------------------------------------------------- slot cá nhân


def test_slotId_withUser_isPersonalAndOnlyThatUserSeesIt():
    model_id = realtime_slots.slot_id("hoa-de", TENANT_A, EDITOR["id"])
    assert realtime_slots.is_personal(model_id)
    assert realtime_slots.visible_to(model_id, TENANT_A, EDITOR["id"]) is True
    assert realtime_slots.visible_to(model_id, TENANT_A, MEMBER["id"]) is False
    assert realtime_slots.visible_to(model_id, TENANT_B, EDITOR["id"]) is False
    assert realtime_slots.visible_to(model_id, None, None) is False


def test_slotId_personalInCommunity_isNotTheSharedSlot():
    assert realtime_slots.slot_id("hoa-de", "default", EDITOR["id"]) != "hoa-de"


def test_updateRegistry_personalPromotion_keepsOrganisationAndSharedModels(monkeypatch, tmp_path):
    ca_nhan = realtime_slots.slot_id("hoa-de", TENANT_A, MEMBER["id"])
    out = _promote_into(monkeypatch, tmp_path, [_entry("hoa-de"), _entry(f"hoa-de@{TENANT_A}")], ca_nhan)
    assert set(out) == {"hoa-de", f"hoa-de@{TENANT_A}", ca_nhan}


def _promote_as(monkeypatch, user, chu_chay, bien_tap=False):
    """Gọi endpoint promote tới cổng quyền; job chưa xong nên 409 nghĩa là đã qua cổng."""
    job = SimpleNamespace(status="running")

    async def _nap(_id):
        return {"job": job, "tenant_id": TENANT_A}

    monkeypatch.setattr(training, "_ensure_job_loaded", _nap)
    monkeypatch.setattr(training, "_la_bien_tap", lambda _u, _t: bien_tap)
    monkeypatch.setattr(training, "_la_nguoi_chay_job", lambda _j, u: u == chu_chay)
    with pytest.raises(HTTPException) as err:
        asyncio.run(training.promote_training_job("j1", user))
    return err.value.status_code


def test_promote_memberOwnJob_passesTheGate(monkeypatch):
    assert _promote_as(monkeypatch, MEMBER, MEMBER["id"]) == 409


def test_promote_memberOtherPersonsJob_returns403(monkeypatch):
    assert _promote_as(monkeypatch, MEMBER, EDITOR["id"]) == 403


def test_promote_editorOtherPersonsJob_passesTheGate(monkeypatch):
    assert _promote_as(monkeypatch, EDITOR, MEMBER["id"], bien_tap=True) == 409


def test_promote_apiKey_returns403(monkeypatch):
    assert _promote_as(monkeypatch, API_KEY, API_KEY["id"], bien_tap=True) == 403


# --------------------------------------------------------------------------- rà soát 06/11


def _promote_community(monkeypatch, user):
    """Như `_promote_as`, nhưng job thuộc Community: 409 nghĩa là đã qua cổng."""
    async def _nap(_id):
        return {"job": SimpleNamespace(status="running"), "tenant_id": "default"}

    monkeypatch.setattr(training, "_ensure_job_loaded", _nap)
    monkeypatch.setattr(training, "_la_bien_tap", lambda _u, _t: True)
    monkeypatch.setattr(training, "_la_nguoi_chay_job", lambda _j, _u: False)
    with pytest.raises(HTTPException) as err:
        asyncio.run(training.promote_training_job("j1", user))
    return err.value.status_code


def test_promote_communityEditorNotAdmin_cannotTakeTheSharedSlot(monkeypatch):
    """Slot `hoa-de` mọi tổ chức và khách đều dùng; biên tập viên Community chỉ có slot riêng."""
    assert _promote_community(monkeypatch, EDITOR) == 403


def test_promote_platformAdminInCommunity_passesTheGate(monkeypatch):
    assert _promote_community(monkeypatch, {**EDITOR, "is_admin": True}) == 409


def test_updateRegistry_manyMembersAtOnce_keepsEveryEntry(monkeypatch, tmp_path):
    """Không khoá thì lượt ghi sau xoá mất entry của lượt trước."""
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "models.json"
    path.write_text(json.dumps({"schema_version": "1", "models": []}), encoding="utf-8")
    monkeypatch.setattr(training, "REGISTRY_PATH", path)
    slots = [realtime_slots.slot_id("hoa-de", TENANT_A, f"nguoi-{i}") for i in range(12)]

    def _ghi(slot):
        return training._update_registry(slot, "checkpoints/x.pt", "Tên", {}, "hoa-de", "vn")

    with ThreadPoolExecutor(max_workers=12) as pool:
        assert all(pool.map(_ghi, slots))
    con_lai = {m["id"] for m in json.loads(path.read_text(encoding="utf-8"))["models"]}
    assert con_lai == set(slots)


def test_entriesOfSlot_personalSlot_ignoresOrganisationSlot(monkeypatch, tmp_path):
    path = tmp_path / "models.json"
    ca_nhan = realtime_slots.slot_id("hoa-de", TENANT_A, MEMBER["id"])
    path.write_text(json.dumps({"models": [_entry(f"hoa-de@{TENANT_A}"), _entry(ca_nhan)]}), encoding="utf-8")
    monkeypatch.setattr(training, "REGISTRY_PATH", path)
    assert [m["id"] for m in training._entries_of_slot(ca_nhan, "hoa-de")] == [ca_nhan]


def test_restoreSlot_rejectedModel_bringsBackTheRunningOneAndKeepsOthers(monkeypatch, tmp_path):
    slot = f"hoa-de@{TENANT_A}"
    cu = {**_entry(slot), "checkpoint_path": "checkpoints/cu.pt"}
    _promote_into(monkeypatch, tmp_path, [cu, _entry(f"hoa-de@{TENANT_B}")], slot)
    training._restore_slot(slot, [cu])
    out = {m["id"]: m for m in json.loads(training.REGISTRY_PATH.read_text(encoding="utf-8"))["models"]}
    assert out[slot]["checkpoint_path"] == "checkpoints/cu.pt"
    assert f"hoa-de@{TENANT_B}" in out


class _ClientGia:
    def __init__(self, ma):
        self.ma = ma

    def __call__(self, **_k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def post(self, *_a, **_k):
        return SimpleNamespace(status_code=self.ma, text="dialect mismatch")


def test_notifyReload_modelRejected_raisesSoPromoteCanUndo(monkeypatch):
    monkeypatch.setattr(training.httpx, "Client", _ClientGia(422))
    with pytest.raises(training._ReloadRejected):
        training._notify_realtime_service_reload("m", "/c.pt", "v")


def test_notifyReload_serviceBroken_keepsEntryForNextStart(monkeypatch):
    """Realtime lỗi 5xx không nói gì về model; đừng gỡ một model có thể vẫn tốt."""
    monkeypatch.setattr(training.httpx, "Client", _ClientGia(503))
    assert training._notify_realtime_service_reload("m", "/c.pt", "v") is False


def test_jobFromDbRow_carriesTheOwner_soTheUiNeedNotAskPerViewer():
    """Giao diện so cột này với người đang xem, kể cả ở cập nhật qua WebSocket."""
    job = training._job_from_db_row({"job_id": "j1", "auth_user_id": MEMBER["id"], "config": {}})
    assert job.auth_user_id == MEMBER["id"]


def test_resolveUser_askedTwiceOnOneRequest_looksUpOnce(monkeypatch):
    """`/realtime/predict` hỏi lại câu này ở mỗi khung hình."""
    from app import access_gate

    so_lan = []
    monkeypatch.setattr(access_gate, "_tra_nguoi_goi", lambda _r: so_lan.append(1) or MEMBER)
    request = SimpleNamespace(state=SimpleNamespace())
    assert access_gate._resolve_user(request) is MEMBER
    assert access_gate._resolve_user(request) is MEMBER
    assert len(so_lan) == 1


def test_resolveUser_guest_isRememberedToo(monkeypatch):
    from app import access_gate

    so_lan = []
    monkeypatch.setattr(access_gate, "_tra_nguoi_goi", lambda _r: so_lan.append(1))
    request = SimpleNamespace(state=SimpleNamespace())
    assert access_gate._resolve_user(request) is None
    assert access_gate._resolve_user(request) is None
    assert len(so_lan) == 1


@pytest.mark.parametrize("chu", [TENANT_A, None])
def test_auditTaskFailure_workerChildDied_stillWritesUnderAScope(monkeypatch, chu):
    """Tiến trình con chết thì tín hiệu bắn từ tiến trình cha, nơi chưa có phạm vi nào."""
    from app import audit, task_registry, tenant_context, worker
    from app.tenant_context import current_tenant, in_system_scope

    da_ghi = []
    monkeypatch.setattr(audit, "record", lambda *_a, **_k: da_ghi.append((current_tenant(), in_system_scope())))
    monkeypatch.setattr(task_registry, "owners_of", lambda ids: {i: chu for i in ids})
    # Bộ test chạy sẵn trong system scope; tiến trình cha thì không có phạm vi nào.
    bo_tenant, bo_system = tenant_context._tenant.set(None), tenant_context._system.set(False)
    try:
        assert not current_tenant() and not in_system_scope()
        worker.audit_task_failure(sender=SimpleNamespace(name="viec"), task_id="t1", exception=MemoryError("het"))
    finally:
        tenant_context._tenant.reset(bo_tenant)
        tenant_context._system.reset(bo_system)
    assert da_ghi == ([(TENANT_A, False)] if chu else [(None, True)])


@pytest.mark.parametrize("duong_dan", ["/2fa/enroll", "/2fa/confirm", "/2fa/disable", "/2fa/recovery-codes",
                                       "/me/exports", "/presence"])
def test_selfServiceWrite_personalActions_needNoTenantRole(duong_dan):
    """Việc của riêng mình không được đợi ai cấp vai."""
    from app.access_gate import _is_self_service_write

    assert _is_self_service_write(duong_dan) is True


@pytest.mark.parametrize("duong_dan", ["/me/exports/x/download", "/upload/video", "/training/start",
                                       "/classes/request", "/tenants/self-serve"])
def test_selfServiceWrite_workOnSharedData_staysBehindTheGate(duong_dan):
    """Cổng này cố ý: ghi vào dữ liệu chung thì phải có ít nhất một vai."""
    from app.access_gate import _is_self_service_write

    assert _is_self_service_write(duong_dan) is False


# --------------------------------------------------------------------------- model riêng


def _job_rieng(chu=MEMBER["id"], da_de_nghi=None, status="completed"):
    config = SimpleNamespace(personal=True, review_requested_at=da_de_nghi)
    return SimpleNamespace(id="j1", auth_user_id=chu, config=config, status=status)


def test_choXem_personalJob_ownerSeesIt():
    assert training._cho_xem(_job_rieng(), MEMBER["id"], False) is True


def test_choXem_personalJob_otherMemberDoesNot():
    assert training._cho_xem(_job_rieng(), "nguoi-khac", False) is False


def test_choXem_personalJobNotSubmitted_reviewerDoesNot():
    assert training._cho_xem(_job_rieng(), EDITOR["id"], True) is False


def test_choXem_submittedJob_reviewerSeesItButOtherMemberDoesNot():
    job = _job_rieng(da_de_nghi="2026-11-07T10:00:00")
    assert training._cho_xem(job, EDITOR["id"], True) is True
    assert training._cho_xem(job, "nguoi-khac", False) is False


def test_choXem_ordinaryJob_everyoneInTheTenant():
    job = SimpleNamespace(auth_user_id=MEMBER["id"], config=SimpleNamespace(personal=False))
    assert training._cho_xem(job, "nguoi-khac", False) is True


def _nap_job(monkeypatch, job, tenant=TENANT_A, trong_db=None):
    async def _nap(_id):
        return {"job": job, "tenant_id": tenant}

    monkeypatch.setattr(training, "_ensure_job_loaded", _nap)
    monkeypatch.setattr(metadata_db, "get_training_job", lambda _id: trong_db)


def test_jobCua_someoneElsesPersonalJob_looksMissing(monkeypatch):
    _nap_job(monkeypatch, _job_rieng())
    monkeypatch.setattr(training, "_duyet_duoc", lambda _u, _t: False)
    assert asyncio.run(training._job_cua("j1", {"id": "nguoi-khac"})) is None


def test_jobCua_requestWrittenByOtherWorker_reviewerStillSeesIt(monkeypatch):
    """Mỗi tiến trình backend có cache riêng; job đã kết thúc không đọc lại DB."""
    job = _job_rieng()
    moi = {"job_id": "j1", "status": "completed", "auth_user_id": MEMBER["id"],
           "config": {"personal": True, "review_requested_at": "2026-11-07T10:00:00"}}
    _nap_job(monkeypatch, job, trong_db=moi)
    monkeypatch.setattr(training, "_duyet_duoc", lambda _u, _t: True)
    assert asyncio.run(training._job_cua("j1", EDITOR)) is not None


def _quyen(monkeypatch, bien_tap):
    monkeypatch.setattr(training, "_la_bien_tap", lambda _u, _t: bien_tap)


def test_duyetDuoc_organisationEditor_yes(monkeypatch):
    _quyen(monkeypatch, True)
    assert training._duyet_duoc(EDITOR, TENANT_A) is True


def test_duyetDuoc_communityEditor_no(monkeypatch):
    """Slot của Community mọi tổ chức cùng dùng: duyệt là việc của quản trị nền tảng."""
    _quyen(monkeypatch, True)
    assert training._duyet_duoc(EDITOR, "default") is False
    assert training._duyet_duoc({**EDITOR, "is_admin": True}, "default") is True


def test_duyetDuoc_member_no(monkeypatch):
    _quyen(monkeypatch, False)
    assert training._duyet_duoc(MEMBER, TENANT_A) is False


def _cho_review(monkeypatch, job, bien_tap=False):
    from app import audit, notifications, tenant_admin

    ghi, bao = [], []
    _nap_job(monkeypatch, job)
    async def _qua(_id, _u):
        return {"job": job, "tenant_id": TENANT_A}

    monkeypatch.setattr(training, "_job_cua", _qua)
    monkeypatch.setattr(training, "_duyet_duoc", lambda _u, _t: bien_tap)
    monkeypatch.setattr(tenant_admin, "model_reviewer_ids", lambda _t: [EDITOR["id"]])
    monkeypatch.setattr(metadata_db, "update_training_job_config", lambda _id, doi: ghi.append(doi))
    monkeypatch.setattr(notifications, "notify", lambda nguoi, *_a, **_k: bao.append(nguoi))
    monkeypatch.setattr(audit, "record", lambda *_a, **_k: None)
    return ghi, bao


def test_requestReview_owner_savesAndTellsTheReviewers(monkeypatch):
    job = _job_rieng()
    ghi, bao = _cho_review(monkeypatch, job)
    asyncio.run(training.request_shared_review("j1", MEMBER))
    assert job.config.review_requested_at
    assert ghi == [{"review_requested_at": job.config.review_requested_at}]
    assert bao == [EDITOR["id"]]


def test_requestReview_askedTwice_tellsReviewersOnce(monkeypatch):
    job = _job_rieng()
    _ghi, bao = _cho_review(monkeypatch, job)
    asyncio.run(training.request_shared_review("j1", MEMBER))
    asyncio.run(training.request_shared_review("j1", MEMBER))
    assert len(bao) == 1


def test_requestReview_notTheOwner_returns403(monkeypatch):
    _cho_review(monkeypatch, _job_rieng(chu="nguoi-khac"))
    with pytest.raises(HTTPException) as err:
        asyncio.run(training.request_shared_review("j1", MEMBER))
    assert err.value.status_code == 403


def test_requestReview_jobStillRunning_returns409(monkeypatch):
    _cho_review(monkeypatch, _job_rieng(status="running"))
    with pytest.raises(HTTPException) as err:
        asyncio.run(training.request_shared_review("j1", MEMBER))
    assert err.value.status_code == 409


def test_rejectReview_reviewer_jobGoesBackToBeingPersonal(monkeypatch):
    job = _job_rieng(da_de_nghi="2026-11-07T10:00:00")
    ghi, bao = _cho_review(monkeypatch, job, bien_tap=True)
    asyncio.run(training.reject_shared_review("j1", training.ReviewReject(reason="chua on"), EDITOR))
    assert job.config.review_requested_at is None and job.config.personal is True
    assert ghi == [{"personal": True, "review_requested_at": None}]
    assert bao == [MEMBER["id"]]


def test_rejectReview_notAReviewer_returns403(monkeypatch):
    _cho_review(monkeypatch, _job_rieng(da_de_nghi="2026-11-07T10:00:00"), bien_tap=False)
    with pytest.raises(HTTPException) as err:
        asyncio.run(training.reject_shared_review("j1", training.ReviewReject(), MEMBER))
    assert err.value.status_code == 403


def test_chiChuHoacBienTap_otherMember_returns403(monkeypatch):
    _quyen(monkeypatch, False)
    monkeypatch.setattr(training, "_la_nguoi_chay_job", lambda _j, _u: False)
    with pytest.raises(HTTPException) as err:
        asyncio.run(training._chi_chu_hoac_bien_tap("j1", MEMBER, TENANT_A))
    assert err.value.status_code == 403


def test_chiChuHoacBienTap_jobOwner_passes(monkeypatch):
    _quyen(monkeypatch, False)
    monkeypatch.setattr(training, "_la_nguoi_chay_job", lambda _j, _u: True)
    asyncio.run(training._chi_chu_hoac_bien_tap("j1", MEMBER, TENANT_A))


def test_chiChuHoacBienTap_editor_passes(monkeypatch):
    _quyen(monkeypatch, True)
    asyncio.run(training._chi_chu_hoac_bien_tap("j1", EDITOR, TENANT_A))


def test_duyetDuoc_apiKey_noAndNeverLooksUpARole(monkeypatch):
    """Id của khoá API không phải UUID: đem tra vai là `/training/start` trả 500."""
    def _khong_duoc_goi(_u, _t):
        raise AssertionError("khong duoc tra vai cho khoa API")

    monkeypatch.setattr(training, "_la_bien_tap", _khong_duoc_goi)
    assert training._duyet_duoc(API_KEY, TENANT_A) is False
