"""Hàng đợi kiểm duyệt và hai cái nút — ai bấm được, và bấm rồi thì đổi gì.

Xem docs/01-architecture/COMMUNITY_MODERATION.md §6, §7.

Hai bài quan trọng nhất ở đây:

* `test_quyet_dinh_ghi_vao_CA_CSV_lan_Postgres` — `samples.csv` là nguồn sự
  thật, Postgres là bản sao. Một quyết định chỉ ghi vào cơ sở dữ liệu sẽ bị
  lượt đồng bộ kế tiếp xoá lặng lẽ.
* `test_community_reviewer_duyet_duoc` — vai ấy KHÔNG có bản sao ở sổ cũ, nên
  một phép kiểm quyền chỉ đọc `tenant_members.role` sẽ từ chối đúng cái vai vừa
  được tạo ra để duyệt.
"""

from __future__ import annotations

import uuid

import pytest

from app import moderation_admin
from app.moderation import APPROVED, PENDING, REJECTED
from app.storage import metadata_db as db
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


def _role_id(code: str) -> str:
    with system_scope("test: tra role_id"):
        rows = db._fetch_all(
            "SELECT role_id FROM roles WHERE role_code = %s AND is_active", (code,))
    assert rows, f"vai {code} chua duoc seed"
    return str(rows[0]["role_id"])


@pytest.fixture
def tai_khoan():
    tao: list[str] = []

    def _make(*, is_admin: bool = False) -> dict:
        from app.auth import create_user

        name = f"md{uuid.uuid4().hex[:10]}"
        u = create_user(username=name, email=f"{name}@example.test",
                        password="correct horse battery", is_admin=is_admin)
        tao.append(str(u["id"]))
        return u

    yield _make

    with system_scope("test cleanup: tai khoan"):
        for uid in tao:
            db._execute("UPDATE samples SET reviewed_by = NULL WHERE reviewed_by = %s",
                        (uid,))
            db._execute("DELETE FROM role_assignments WHERE user_id = %s", (uid,))
            db._execute("DELETE FROM memberships WHERE user_id = %s", (uid,))
            db._execute("DELETE FROM notifications WHERE user_id = %s", (uid,))
            db._execute("DELETE FROM users WHERE id = %s", (uid,))


def _cap_vai_v5(user_id: str, role_code: str) -> None:
    """Cấp vai ở phạm vi COMMUNITY — nơi `community_reviewer` được phép gán.

    Bảo đảm tenant cộng đồng đang HOẠT ĐỘNG trước khi gán, chứ không giả định.
    `can_moderate` (đúng như vậy) từ chối grant thuộc một tổ chức đã ngừng hoạt
    động, và `signdb_test` là CSDL dùng chung: một bài khác đình chỉ tenant ấy
    rồi không hoàn lại sẽ làm bài này đỏ vì một lý do chẳng liên quan gì tới
    thứ nó đang kiểm. Đo 21/08/2026: `community.is_active = FALSE` trong CSDL
    test, `TRUE` trên sản xuất và `TRUE` ở mặc định của cột.
    """
    from app.storage.authz_schema import COMMUNITY_TENANT_ID

    with system_scope("test: bao dam tenant cong dong dung duoc"):
        db._execute(
            "UPDATE tenants SET is_active = TRUE, deleted_at = NULL "
            " WHERE tenant_id = %s", (COMMUNITY_TENANT_ID,))

    with system_scope("test: cap vai kiem duyet"):
        rows = db._fetch_all(
            "INSERT INTO memberships (user_id, scope_level, tenant_id, legacy_role, "
            "                         status, joined_at) "
            "VALUES (%s, 'TENANT', %s, NULL, 'ACTIVE', NOW()) RETURNING membership_id",
            (user_id, COMMUNITY_TENANT_ID))
        db._execute(
            "INSERT INTO role_assignments (user_id, role_id, membership_id, "
            "                              assigned_by_user_id) VALUES (%s,%s,%s,%s)",
            (user_id, _role_id(role_code), str(rows[0]["membership_id"]), user_id))


@pytest.fixture
def phien_cho_duyet(tai_khoan):
    """Một phiên thu 3 mẫu đang chờ duyệt, kèm người đóng góp."""
    nguoi = tai_khoan()
    tag = uuid.uuid4().hex[:8]
    class_uid = f"modtest_cls_{tag}"
    session_id = str(uuid.uuid4())
    uids = [uuid.uuid4().hex[:10] for _ in range(3)]

    with system_scope("test: dung phien cho duyet"):
        db._execute(
            "INSERT INTO classes (tenant_id, class_uid, slug, label_original) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (DEFAULT_TENANT_ID, class_uid, f"modtest-{tag}", "nhan thu nghiem"))
        # `class_uid` và `session_id` là NOT NULL — bảng này ghi lại một lần
        # quay THẬT, và một lần quay luôn thuộc về một lớp.
        db._execute(
            "INSERT INTO capture_sessions (capture_session_id, tenant_id, class_uid, "
            "                              session_id, auth_user_id) "
            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (session_id, DEFAULT_TENANT_ID, class_uid, f"s-{tag}", str(nguoi["id"])))
        for i, uid in enumerate(uids):
            db._execute(
                "INSERT INTO samples (tenant_id, sample_uid, class_uid, auth_user_id, "
                "                     capture_session_id, augment_id, review_status, "
                "                     label_original, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())",
                (DEFAULT_TENANT_ID, uid, class_uid, str(nguoi["id"]), session_id,
                 i, PENDING, "nhan thu nghiem"))

    yield {"session_id": session_id, "uids": uids, "nguoi": nguoi,
           "class_uid": class_uid}

    with system_scope("test cleanup: phien"):
        db._execute("DELETE FROM samples WHERE sample_uid = ANY(%s)", (uids,))
        db._execute("DELETE FROM capture_sessions WHERE capture_session_id = %s",
                    (session_id,))
        db._execute("DELETE FROM classes WHERE tenant_id = %s AND class_uid = %s",
                    (DEFAULT_TENANT_ID, class_uid))


def _trang_thai(uid: str) -> str:
    with system_scope("test: doc trang thai"):
        rows = db._fetch_all(
            "SELECT review_status FROM samples WHERE sample_uid = %s", (uid,))
    return str(rows[0]["review_status"])


# ---------------------------------------------------------------------------
# Ai được duyệt
# ---------------------------------------------------------------------------


class TestAiDuocDuyet:
    def test_quan_tri_nen_tang_duoc(self, tai_khoan):
        assert moderation_admin.can_moderate(tai_khoan(is_admin=True)) is True

    def test_community_reviewer_duyet_duoc(self, tai_khoan):
        """Vai này KHÔNG có bản sao ở sổ cũ.

        `tenant_members.role` chỉ nhận `admin|editor|NULL`, nên một phép kiểm
        chỉ đọc cột ấy — tức `authorize()` trong shadow mode — sẽ từ chối đúng
        cái vai vừa được tạo ra để duyệt.
        """
        u = tai_khoan()
        _cap_vai_v5(str(u["id"]), "community_reviewer")

        assert moderation_admin.can_moderate(u) is True

    def test_tai_khoan_thuong_KHONG_duoc(self, tai_khoan):
        assert moderation_admin.can_moderate(tai_khoan()) is False

    def test_community_member_KHONG_duoc(self, tai_khoan):
        """Người đóng góp không tự duyệt dữ liệu của chính mình."""
        u = tai_khoan()
        _cap_vai_v5(str(u["id"]), "community_member")

        assert moderation_admin.can_moderate(u) is False

    def test_vai_bi_thu_hoi_thi_mat_quyen(self, tai_khoan):
        u = tai_khoan()
        _cap_vai_v5(str(u["id"]), "community_reviewer")
        with system_scope("test: thu hoi"):
            db._execute(
                "UPDATE role_assignments SET revoked_at = NOW(), "
                "       revoked_by_user_id = %s WHERE user_id = %s",
                (str(u["id"]), str(u["id"])))

        assert moderation_admin.can_moderate(u) is False

    def test_khong_co_id_thi_tu_choi(self):
        assert moderation_admin.can_moderate({}) is False


# ---------------------------------------------------------------------------
# Hàng đợi
# ---------------------------------------------------------------------------


class TestHangDoi:
    def test_phien_hien_ra_MOT_lan_du_co_ba_mau(self, phien_cho_duyet):
        """Đơn vị là phiên. Ba mẫu cùng phiên phải gộp thành một dòng, nếu
        không hàng đợi 250 mục biến thành 3.862 mục."""
        rows = moderation_admin.list_pending_sessions(DEFAULT_TENANT_ID, limit=500)

        cua_ta = [r for r in rows
                  if str(r["capture_session_id"]) == phien_cho_duyet["session_id"]]
        assert len(cua_ta) == 1
        assert int(cua_ta[0]["sample_count"]) == 3

    def test_dem_theo_PHIEN_chu_khong_theo_mau(self, phien_cho_duyet):
        n = moderation_admin.pending_session_count(DEFAULT_TENANT_ID)
        rows = moderation_admin.list_pending_sessions(DEFAULT_TENANT_ID, limit=500)

        assert n == len(rows), "huy hieu va danh sach phai noi cung mot con so"

    def test_mau_goc_duoc_neu_ra_de_xem_lai(self, phien_cho_duyet):
        """Người duyệt xem MỘT lần quay, không phải mười một bản tăng cường."""
        rows = moderation_admin.list_pending_sessions(DEFAULT_TENANT_ID, limit=500)
        cua_ta = next(r for r in rows
                      if str(r["capture_session_id"]) == phien_cho_duyet["session_id"])

        assert str(cua_ta["original_uid"]) == phien_cho_duyet["uids"][0]


# ---------------------------------------------------------------------------
# Quyết định
# ---------------------------------------------------------------------------


class TestQuyetDinh:
    def test_duyet_doi_MOI_mau_trong_phien(self, phien_cho_duyet, tai_khoan):
        nguoi_duyet = tai_khoan(is_admin=True)

        kq = moderation_admin.decide_session(
            phien_cho_duyet["session_id"], approve=True,
            actor_id=str(nguoi_duyet["id"]), tenant_id=DEFAULT_TENANT_ID)

        assert kq["sample_count"] == 3
        for uid in phien_cho_duyet["uids"]:
            assert _trang_thai(uid) == APPROVED

    def test_tu_choi_KHONG_xoa_gi(self, phien_cho_duyet, tai_khoan):
        """Dữ liệu vẫn thuộc về người đóng góp — chỉ không được dùng chung."""
        nguoi_duyet = tai_khoan(is_admin=True)

        moderation_admin.decide_session(
            phien_cho_duyet["session_id"], approve=False,
            actor_id=str(nguoi_duyet["id"]), tenant_id=DEFAULT_TENANT_ID,
            note="Tay khuat khoi khung hinh.")

        for uid in phien_cho_duyet["uids"]:
            assert _trang_thai(uid) == REJECTED
            with system_scope("test: mau con do khong"):
                assert db._fetch_all(
                    "SELECT 1 FROM samples WHERE sample_uid = %s AND deleted_at IS NULL",
                    (uid,))

    def test_tu_choi_KHONG_kem_ly_do_thi_bi_chan(self, phien_cho_duyet, tai_khoan):
        """Từ chối suông thì người đóng góp không có gì để sửa."""
        nguoi_duyet = tai_khoan(is_admin=True)

        with pytest.raises(moderation_admin.ModerationError):
            moderation_admin.decide_session(
                phien_cho_duyet["session_id"], approve=False,
                actor_id=str(nguoi_duyet["id"]), tenant_id=DEFAULT_TENANT_ID,
                note="   ")

        assert _trang_thai(phien_cho_duyet["uids"][0]) == PENDING

    def test_phien_cua_tenant_KHAC_khong_dong_toi_duoc(self, phien_cho_duyet,
                                                       tai_khoan):
        """Phạm vi là hàng rào, không phải bộ lọc hiển thị."""
        nguoi_duyet = tai_khoan(is_admin=True)

        with pytest.raises(moderation_admin.ModerationError):
            moderation_admin.decide_session(
                phien_cho_duyet["session_id"], approve=True,
                actor_id=str(nguoi_duyet["id"]), tenant_id="tenant-khong-ton-tai")

        assert _trang_thai(phien_cho_duyet["uids"][0]) == PENDING

    def test_nguoi_dong_gop_nhan_duoc_thong_bao(self, phien_cho_duyet, tai_khoan):
        """Thiếu nó thì lời hứa "qua kiểm duyệt mới công khai" vô hình với đúng
        người cần biết, và họ đi hỏi qua kênh hỗ trợ."""
        nguoi_duyet = tai_khoan(is_admin=True)

        moderation_admin.decide_session(
            phien_cho_duyet["session_id"], approve=True,
            actor_id=str(nguoi_duyet["id"]), tenant_id=DEFAULT_TENANT_ID)

        with system_scope("test: doc thong bao"):
            rows = db._fetch_all(
                "SELECT kind, severity FROM notifications WHERE user_id = %s",
                (str(phien_cho_duyet["nguoi"]["id"]),))
        assert any(r["kind"] == "moderation" for r in rows)

    def test_MOT_thong_bao_cho_MOT_phien_khong_phai_ba(self, phien_cho_duyet,
                                                       tai_khoan):
        """Bắn theo mẫu sẽ tạo 11 thông báo cho một lần quay, và cái chuông trở
        thành thứ người ta tắt đi."""
        nguoi_duyet = tai_khoan(is_admin=True)

        moderation_admin.decide_session(
            phien_cho_duyet["session_id"], approve=True,
            actor_id=str(nguoi_duyet["id"]), tenant_id=DEFAULT_TENANT_ID)

        with system_scope("test: dem thong bao"):
            rows = db._fetch_all(
                "SELECT count(*) AS n FROM notifications "
                " WHERE user_id = %s AND kind = 'moderation'",
                (str(phien_cho_duyet["nguoi"]["id"]),))
        assert int(rows[0]["n"]) == 1
