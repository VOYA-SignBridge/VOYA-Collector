"""Ba tính năng thêm ngày 15/09/2026, và ranh giới mỗi cái phải giữ.

Chạy:
    sh scripts/run_tests.sh backend/tests/test_personal_export_and_visibility.py -q

1. `capture_sessions.visibility` — chủ phiên tự mở phiên của mình cho thành
   viên thường cùng tổ chức. Ranh giới: thành viên thường xin "cả tổ chức" chỉ
   thấy phiên của mình + phiên người khác ĐÃ mở; biên tập viên vẫn thấy hết;
   không ai đổi được cờ trên phiên của người khác nếu không có vai biên tập.

2. `personal_export` — "cho tôi tệp của chính tôi". Ranh giới: gói chỉ chứa
   dòng có `auth_user_id` = người gọi, kèm tệp .npz thật của đúng những dòng
   ấy; người khác không tải được bản xuất không phải của mình.

3. Cam kết sử dụng khi xuất dữ liệu TỔ CHỨC (`agree`) và dấu vết kiểm toán.
   Ranh giới: không có `agree=true` thì không có hàng `tenant_exports` nào; có
   thì phải có đúng một dòng `tenant.export_requested` mang số hiệu cam kết.

Mọi hàng do test tạo mang tiền tố `pytest-pev-` và được dọn ở mọi đường ra.
"""

from __future__ import annotations

import csv
import io
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.storage import metadata_db as db
from app.modules.saas.tenant_context import system_scope, tenant_scope

# ---------------------------------------------------------------------------
# fixture: một tổ chức, hai người (A, B), một lớp, ba phiên thu
# ---------------------------------------------------------------------------


@pytest.fixture
def to_chuc():
    """A và B là thành viên thường (không vai). Ba phiên thu:

        s_a_kin    của A, private  (mặc định)
        s_b_mo     của B, 'tenant' (B đã tự mở)
        s_b_kin    của B, private
    """
    from tests.conftest import purge_tenant

    sfx = uuid.uuid4().hex[:8]
    tid = f"pytest-pev-{sfx}"
    cls = f"cls_pev_{sfx}"
    d: dict = {"tid": tid, "cls": cls}

    with system_scope("test: dung fixture xuat ca nhan"), db._cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id, display_name, slug) VALUES (%s,%s,%s)",
                    (tid, f"pytest pev {sfx}", tid))
        for key in ("a", "b"):
            cur.execute(
                "INSERT INTO users (id, username, email, password_hash, tenant_id) "
                "VALUES (gen_random_uuid(), %s, %s, 'x', %s) RETURNING id",
                (f"pytest-pev-{key}-{sfx}", f"pytest-pev-{key}-{sfx}@example.invalid", tid))
            d[key] = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant_members (tenant_id, user_id, role) VALUES (%s,%s,NULL)",
                        (tid, d[key]))
        cur.execute(
            "INSERT INTO classes (class_uid, tenant_id, slug, label_original, language, "
            "region, is_active) VALUES (%s,%s,'pev','PEV','vn','common',true)", (cls, tid))

        def phien(owner: str, vis: str) -> str:
            sid = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO capture_sessions (capture_session_id, tenant_id, class_uid, "
                "session_id, auth_user_id, visibility, started_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,NOW())",
                (sid, tid, cls, f"code-{uuid.uuid4().hex[:6]}", owner, vis))
            return sid

        d["s_a_kin"] = phien(d["a"], "private")
        d["s_b_mo"] = phien(d["b"], "tenant")
        d["s_b_kin"] = phien(d["b"], "private")

    try:
        yield d
    finally:
        purge_tenant(tid)
        with system_scope("test: don tai khoan pev"), db._cursor() as cur:
            cur.execute("DELETE FROM audit_log WHERE actor_user_id::text = ANY(%s)",
                        ([d["a"], d["b"]],))
            cur.execute("DELETE FROM users WHERE id::text = ANY(%s)", ([d["a"], d["b"]],))


def _nguoi(uid: str, *, role=None, is_admin=False) -> dict:
    return {"id": uid, "username": f"u-{uid[:6]}", "email": "x@x", "is_active": True,
            "is_admin": is_admin, "tenant_role": role}


# ---------------------------------------------------------------------------
# 1. visibility
# ---------------------------------------------------------------------------


def _ids(resp) -> set:
    return {s.capture_session_id for s in resp.sessions}


def test_thanh_vien_thuong_xin_ca_to_chuc_chi_thay_cua_minh_va_phien_da_mo(to_chuc):
    """Trước 15/09 đường này trả 403 cho thành viên thường. Nay nó trả một danh
    sách đã LỌC — và phép lọc là thứ phải kiểm: phiên private của B KHÔNG được
    lọt vào mắt A."""
    from app.routers.capture_sessions import list_sessions

    with tenant_scope(to_chuc["tid"]):
        r = list_sessions(scope="tenant", limit=200, current_user=_nguoi(to_chuc["a"]))

    assert r.scope == "tenant"
    assert _ids(r) == {to_chuc["s_a_kin"], to_chuc["s_b_mo"]}, \
        "phien private cua nguoi khac lot vao danh sach"
    mo = next(s for s in r.sessions if s.capture_session_id == to_chuc["s_b_mo"])
    assert mo.visibility == "tenant" and mo.is_mine is False


@pytest.mark.parametrize("role", ["editor", "admin", "owner"])
def test_private_khong_co_ngoai_le_quan_tri(to_chuc, role):
    """Policy 23/09: private chỉ chủ dữ liệu thấy, kể cả người xem có vai cao."""
    from app.routers.capture_sessions import list_sessions

    with tenant_scope(to_chuc["tid"]):
        r = list_sessions(scope="tenant", limit=200,
                          current_user=_nguoi(to_chuc["a"], role=role))
    assert _ids(r) == {to_chuc["s_a_kin"], to_chuc["s_b_mo"]}


def test_scope_mine_khong_doi(to_chuc):
    from app.routers.capture_sessions import list_sessions

    with tenant_scope(to_chuc["tid"]):
        r = list_sessions(scope="mine", limit=200, current_user=_nguoi(to_chuc["b"]))
    assert _ids(r) == {to_chuc["s_b_mo"], to_chuc["s_b_kin"]}


def _visibility_of(sid: str) -> str:
    with system_scope("test: doc visibility"):
        rows = db._fetch_all(
            "SELECT visibility FROM capture_sessions WHERE capture_session_id = %s", (sid,))
    return rows[0]["visibility"]


def test_chu_phien_doi_duoc_co_nguoi_khac_thi_khong(to_chuc):
    from app.routers.capture_sessions import SessionUpdate, update_session

    sid = to_chuc["s_a_kin"]
    with tenant_scope(to_chuc["tid"]):
        # B (không vai) sửa phiên của A: từ chối, và cờ KHÔNG đổi.
        with pytest.raises(HTTPException) as ei:
            update_session(sid, SessionUpdate(visibility="tenant"), None,
                           current_user=_nguoi(to_chuc["b"]))
        assert ei.value.status_code == 404
        assert _visibility_of(sid) == "private"

        # A (chủ phiên) mở phiên của mình.
        update_session(sid, SessionUpdate(visibility="tenant"), None,
                       current_user=_nguoi(to_chuc["a"]))
        assert _visibility_of(sid) == "tenant"

        # ...và giờ B thấy nó khi xin "cả tổ chức".
        from app.routers.capture_sessions import list_sessions
        r = list_sessions(scope="tenant", limit=200, current_user=_nguoi(to_chuc["b"]))
        assert sid in _ids(r)


def test_readable_samples_follow_live_session_visibility(to_chuc, tmp_path, monkeypatch):
    from app.routers import dataset
    import numpy as np
    tid, a, b = to_chuc["tid"], to_chuc["a"], to_chuc["b"]
    uids = [uuid.uuid4().hex[:10] for _ in range(3)]
    with tenant_scope(tid):
        for uid, owner, session in zip(uids, [a, b, b], ["s_a_kin", "s_b_mo", "s_b_kin"]):
            db._execute("INSERT INTO samples (sample_uid, tenant_id, class_uid, auth_user_id, capture_session_id) VALUES (%s,%s,%s,%s,%s)",
                        (uid, tid, to_chuc["cls"], owner, to_chuc[session]))
        assert db.get_readable_sample_uids(uids, a, tid) == set(uids[:2])
        db._execute("UPDATE capture_sessions SET visibility = 'private' WHERE capture_session_id = %s", (to_chuc["s_b_mo"],))
        assert db.get_readable_sample_uids(uids, a, tid) == {uids[0]}
        assert db.get_readable_sample_uids(uids, b, tid) == set(uids[1:])
        assert db.get_readable_sample_uids(uids, a, "other-tenant") == set()
        path = tmp_path / "private.npz"
        np.savez_compressed(path, sequence=np.ones((60, 126)))
        monkeypatch.setattr(dataset, "list_samples_v2", lambda tenant: [
            {"sample_uid": uids[2], "file_path": str(path), "class_uid": to_chuc["cls"],
             "review_status": "approved", "auth_user_id": b, "session_id": "private"}])
        # Thành viên thường khác: mẫu private của b vẫn kín.
        actor = _nguoi(a)
        with pytest.raises(HTTPException) as denied:
            dataset.get_sample_data(uids[2], current_user=actor)
        assert denied.value.status_code == 404
        assert dataset.list_samples(current_user=actor) == []
        assert dataset.list_sessions(current_user=actor) == []
        # Chủ mẫu, và người quản lý tenant (chính sách 17/10/2026: `private` kín
        # với thành viên khác, KHÔNG kín với admin/editor của tổ chức).
        for viewer in [_nguoi(b), {**_nguoi(a), "is_admin": True}]:
            response = dataset.get_sample_data(uids[2], current_user=viewer)
            assert response.path == str(path)
            assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("visibility", ["private", "tenant"])
def test_editor_cannot_change_someone_elses_visibility(to_chuc, visibility):
    from app.routers.capture_sessions import SessionUpdate, update_session
    sid = to_chuc["s_b_kin"] if visibility == "private" else to_chuc["s_b_mo"]
    with tenant_scope(to_chuc["tid"]), pytest.raises(HTTPException) as error:
        update_session(sid, SessionUpdate(visibility="community"), None,
                       current_user=_nguoi(to_chuc["a"], role="admin"))
    assert error.value.status_code == (404 if visibility == "private" else 403)
    assert _visibility_of(sid) == visibility


def test_tenant_export_cannot_bypass_private(to_chuc):
    from app.modules.saas import tenant_lifecycle
    with pytest.raises(tenant_lifecycle.LifecycleError) as error:
        tenant_lifecycle.request_export(to_chuc["tid"], requested_by=to_chuc["a"],
                                        scope="full", export_purpose="tenant_portability")
    assert error.value.status_code == 403
    assert _so_ban_xuat(to_chuc["tid"]) == 0


def test_private_cannot_enter_moderation_queue_or_be_approved_by_admin(to_chuc):
    from app.modules.admin import moderation_admin
    tid, sid = to_chuc["tid"], to_chuc["s_b_kin"]
    with tenant_scope(tid):
        db._execute("INSERT INTO samples (sample_uid, tenant_id, class_uid, auth_user_id, capture_session_id, review_status) VALUES (%s,%s,%s,%s,%s,'pending')",
                    (uuid.uuid4().hex[:10], tid, to_chuc["cls"], to_chuc["b"], sid))
        assert moderation_admin.pending_session_count(tid) == 0
        assert moderation_admin.list_pending_sessions(tid) == []
        with pytest.raises(moderation_admin.ModerationError) as error:
            moderation_admin.decide_session(sid, approve=True, actor_id=to_chuc["a"], tenant_id=tid)
        assert error.value.status_code == 404


# ---------------------------------------------------------------------------
# 2. personal export
# ---------------------------------------------------------------------------


def _thu_muc_ra(tmp_path: Path) -> Path:
    """Bản giả lập của `_export_root`: cùng hợp đồng — thư mục PHẢI tồn tại."""
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _dong_mau(uid: str, sample_uid: str, npz: str) -> dict:
    return {"sample_uid": sample_uid, "class_uid": "c", "slug": "c", "label_original": "C",
            "language": "vn", "dialect": "common", "source_type": "camera",
            "file_path": f"features/vn/common/c_x/{npz}", "auth_user_id": uid}


def test_goi_ca_nhan_chi_chua_dong_va_tep_cua_dung_nguoi_do(to_chuc, tmp_path, monkeypatch):
    """Lõi của tính năng, và là lời hứa trong README của gói: "chỉ dữ liệu bạn
    đã tự đóng góp". Kho mẫu và cây tệp được giả lập để test không chạm
    `dataset/samples.csv` thật — thứ mà `_restore_dataset_files` phải canh."""
    from app.modules.export import personal_export

    tid, a, b = to_chuc["tid"], to_chuc["a"], to_chuc["b"]
    npz_a, npz_b = f"sample_{uuid.uuid4().hex[:6]}.npz", f"sample_{uuid.uuid4().hex[:6]}.npz"
    rows = [_dong_mau(a, "aaaa000001", npz_a), _dong_mau(b, "bbbb000002", npz_b)]

    monkeypatch.setattr("app.dataset_samples.list_samples", lambda tenant: list(rows))
    import numpy as np
    monkeypatch.setattr("app.config.settings.dataset_root", str(tmp_path))
    tep_a, tep_b = (tmp_path / r["file_path"] for r in rows)
    tep_a.parent.mkdir(parents=True)
    np.savez_compressed(tep_a, sequence=np.ones((60, 126), dtype=np.float32))
    np.savez_compressed(tep_b, sequence=np.ones((60, 126), dtype=np.float32))
    monkeypatch.setattr("app.dataset_manager.iter_tenant_feature_files",
                        lambda tenant: iter([tep_a, tep_b]))
    monkeypatch.setattr(personal_export, "_export_root", lambda: _thu_muc_ra(tmp_path))

    with tenant_scope(tid):
        job = personal_export.request_export(tid, a)
    ket_qua = personal_export.run_export(job["export_id"])
    assert ket_qua["status"] == "ready" and ket_qua["sample_count"] == 1

    with tenant_scope(tid):
        path = personal_export.export_file(tid, a, job["export_id"])
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        assert "samples.csv" in names and "README.txt" in names
        assert f"files/{npz_a}" in names, "thieu tep .npz cua chinh nguoi xuat"
        assert f"files/{npz_b}" not in names, "tep cua nguoi khac lot vao goi"
        doc = list(csv.DictReader(io.StringIO(z.read("samples.csv").decode("utf-8"))))
    assert [r["sample_uid"] for r in doc] == ["aaaa000001"]
    assert doc[0]["auth_user_id"] == a
    assert doc[0]["file_path"] == f"files/{npz_a}"


def test_nguoi_khac_khong_tai_duoc_va_khong_thay_ban_xuat_khong_phai_cua_minh(
        to_chuc, tmp_path, monkeypatch):
    """Một UUID đoán trúng không được trở thành đường tải dữ liệu của người
    khác — `export_file` khoá theo CẢ tenant, user và export_id."""
    from app.modules.export import personal_export

    tid, a, b = to_chuc["tid"], to_chuc["a"], to_chuc["b"]
    monkeypatch.setattr("app.dataset_samples.list_samples", lambda tenant: [])
    monkeypatch.setattr("app.dataset_manager.iter_tenant_feature_files", lambda tenant: iter([]))
    monkeypatch.setattr(personal_export, "_export_root", lambda: _thu_muc_ra(tmp_path))

    with tenant_scope(tid):
        job = personal_export.request_export(tid, a)
    personal_export.run_export(job["export_id"])

    with tenant_scope(tid):
        assert {r["export_id"] for r in personal_export.list_exports(tid, a)} == {job["export_id"]}
        assert personal_export.list_exports(tid, b) == []
        with pytest.raises(personal_export.PersonalExportError) as ei:
            personal_export.export_file(tid, b, job["export_id"])
        assert ei.value.status_code == 404
        assert personal_export.export_file(tid, a, job["export_id"]).exists()


# ---------------------------------------------------------------------------
# 3. cam kết khi xuất dữ liệu TỔ CHỨC + kiểm toán
# ---------------------------------------------------------------------------


@pytest.fixture
def client_quan_tri_to_chuc(to_chuc, monkeypatch):
    """A là quản trị viên CỦA tổ chức (không phải nền tảng), đi qua middleware
    thật bằng token thật — để phạm vi request đúng là tổ chức của A, và dòng
    kiểm toán ghi được dưới RLS."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.modules.saas import saas_tasks
    from app import auth
    from app.routers.tenants import router
    from app.modules.saas.tenant_middleware import TenantScopeMiddleware

    tid, a = to_chuc["tid"], to_chuc["a"]
    with system_scope("test: nang A len quan tri to chuc"):
        db._execute("UPDATE tenant_members SET role = 'admin' WHERE tenant_id = %s AND user_id = %s",
                    (tid, a))
        # Organization export tests below exercise consent on shared data.
        db._execute("UPDATE capture_sessions SET visibility = 'tenant' WHERE tenant_id = %s", (tid,))
    # Không phái tác vụ thật: worker đang chạy là ảnh cũ, và một job thật để
    # lại tệp trên đĩa nằm ngoài tầm dọn của fixture này.
    monkeypatch.setattr(saas_tasks.run_tenant_export, "delay", lambda *_a, **_k: None)

    app = FastAPI()
    app.include_router(router)
    app.add_middleware(TenantScopeMiddleware)
    headers = {"Authorization": f"Bearer {auth.create_access_token({'sub': a})}"}
    with TestClient(app) as c:
        yield c, headers


def _so_ban_xuat(tid: str) -> int:
    with system_scope("test: dem tenant_exports"):
        return int(db._fetch_all("SELECT count(*) AS n FROM tenant_exports WHERE tenant_id = %s",
                                 (tid,))[0]["n"])


def test_khong_dong_y_thi_khong_co_ban_xuat_nao(to_chuc, client_quan_tri_to_chuc):
    """Cả hai vế: bị từ chối, VÀ không có hàng nào được ghi. Một bản vá hỏng
    có thể trả 422 SAU khi đã chèn hàng — nên đếm trước và sau."""
    c, h = client_quan_tri_to_chuc
    tid = to_chuc["tid"]
    truoc = _so_ban_xuat(tid)

    r = c.post(f"/tenants/{tid}/exports", params={"scope": "metadata"}, headers=h)
    assert r.status_code == 422, r.text[:200]                   # thiếu `agree`
    r = c.post(f"/tenants/{tid}/exports", params={"scope": "metadata", "agree": "false"},
               headers=h)
    assert r.status_code == 422 and "cam kết" in r.text
    assert _so_ban_xuat(tid) == truoc


def test_dong_y_thi_co_ban_xuat_va_dung_mot_dong_kiem_toan_mang_so_hieu_cam_ket(
        to_chuc, client_quan_tri_to_chuc):
    from app.routers.tenants import EXPORT_AGREEMENT_VERSION

    c, h = client_quan_tri_to_chuc
    tid, a = to_chuc["tid"], to_chuc["a"]

    r = c.post(f"/tenants/{tid}/exports", params={"scope": "metadata", "agree": "true"},
               headers=h)
    assert r.status_code == 202, r.text[:200]
    export_id = r.json()["export_id"]

    with system_scope("test: doc kiem toan"):
        vet = db._fetch_all(
            "SELECT tenant_id, actor_user_id::text AS actor, detail FROM audit_log "
            "WHERE action = 'tenant.export_requested' AND target_id = %s", (export_id,))
    assert len(vet) == 1, "phai co DUNG MOT dong kiem toan cho lan dat hang nay"
    assert vet[0]["tenant_id"] == tid and vet[0]["actor"] == a
    assert vet[0]["detail"]["agreement_version"] == EXPORT_AGREEMENT_VERSION
    assert vet[0]["detail"]["scope"] == "metadata"


# ---------------------------------------------------------------------------
# 4. tìm tài khoản theo email / tên đăng nhập (vòng nền tảng)
# ---------------------------------------------------------------------------


def test_tim_tai_khoan_khop_mot_phan_va_tu_choi_chuoi_qua_ngan(to_chuc):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.auth import require_admin
    from app.modules.security.rate_limit_deps import limit_catalog
    from app.routers.tenants import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_admin] = lambda: _nguoi(to_chuc["a"], is_admin=True)
    app.dependency_overrides[limit_catalog] = lambda: None
    sfx = to_chuc["tid"].removeprefix("pytest-pev-")

    with TestClient(app) as c:
        r = c.get("/tenants/accounts/search", params={"q": f"pev-b-{sfx}"})
        assert r.status_code == 200, r.text[:200]
        assert {x["id"] for x in r.json()} == {to_chuc["b"]}
        assert all("password" not in x for x in r.json())

        r = c.get("/tenants/accounts/search", params={"q": "x"})
        assert r.status_code == 422                                # min_length=2
