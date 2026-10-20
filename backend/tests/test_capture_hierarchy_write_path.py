"""Phân cấp buổi thu phải được dựng LÚC GHI, không phải lúc migrate.

Vết đã đo trên sản xuất ngày 23/08/2026:

    mẫu quay 2026-08-19 01:15  ->  capture session ra đời 2026-08-23 16:20
                                   (4 ngày 15 giờ)

Không đường ghi nào tạo capture session; chúng chỉ ra đời từ một câu backfill
trong `MIGRATION_STATEMENTS` suy ngược từ `samples`. Backfill là công cụ cho dữ
liệu CŨ, và để nó gánh luôn tính nhất quán của dữ liệu MỚI là nhầm vai.

Tệp này canh hai thứ khác nhau:

    dựng đúng    ghi một mẫu là có ngay buổi thu + phiên thu, đúng tenant
    dựng một lần luỹ đẳng — thử lại, ghi mẫu thứ hai, hay chạy lại backfill
                 đều KHÔNG sinh thêm hàng nào

Chạy trên Postgres thật. Mọi test tự dọn phần mình tạo ra.
"""

from __future__ import annotations

import uuid

import pytest

from app.storage import metadata_db as db
from app.tenant_context import system_scope, tenant_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def to_chuc():
    """Một tenant + một lớp thật, dọn sạch sau khi xong.

    Không dùng giao dịch tự hoàn tác như các tệp khác: `ensure_capture_session`
    tự quản giao dịch của nó (`_fetch_all` mở và đóng một giao dịch mỗi lượt),
    nên muốn quan sát được kết quả thì phải để nó commit thật rồi dọn tay.
    """
    tid = f"test-{uuid.uuid4().hex[:8]}"
    cls = f"cls_{uuid.uuid4().hex[:8]}"
    with system_scope("test: dung to chuc thu nghiem"):
        db._execute("INSERT INTO tenants(tenant_id, display_name, slug) VALUES(%s,%s,%s)",
                    (tid, "Thử ghi", tid))
        db._execute(
            "INSERT INTO classes(class_uid, tenant_id, slug, label_original, "
            "language, region, is_active) VALUES(%s,%s,'g','G','vn','common',true)",
            (cls, tid))
    try:
        yield tid, cls
    finally:
        # Dọn theo `PURGE_ORDER`, KHÔNG theo danh sách bảng tự liệt kê.
        #
        # Bản đầu liệt kê tay bốn bảng và bỏ sót phần còn lại, nên tenant nào
        # chạm tới một bảng ngoài danh sách sẽ không xoá được — khoá ngoại
        # RESTRICT chặn câu `DELETE FROM tenants`, và vì lỗi bị nuốt, nó rò
        # lặng lẽ. Đo ngày 24/08/2026 trên `signdb_test`: **135 tenant** tồn
        # đọng, và chúng làm một test KHÔNG liên quan đỏ — bất biến "mọi tổ
        # chức đang sống đều có đăng ký đang mở" của bộ đọc SOT.
        #
        # `PURGE_ORDER` là nguồn sự thật duy nhất cho thứ tự lá-trước-gốc, và
        # nó được cập nhật mỗi khi có bảng mới. Một bản sao ở đây sẽ trôi khỏi
        # nó ngay lần thêm bảng kế tiếp.
        from app.tenant_lifecycle import PURGE_ORDER

        with system_scope("test: don to chuc thu nghiem"):
            for bang in PURGE_ORDER:
                try:
                    db._execute(f"DELETE FROM {bang} WHERE tenant_id = %s", (tid,))
                except Exception:  # bảng có thể chưa tồn tại ở bản cài tối thiểu
                    pass
            db._execute("DELETE FROM tenants WHERE tenant_id = %s", (tid,))


def _dem(tid, bang):
    with system_scope("test: dem"):
        return db._fetch_all(f"SELECT count(*) AS n FROM {bang} WHERE tenant_id = %s",
                             (tid,))[0]["n"]


# ------------------------------------------------------------------ dựng đúng

def test_ghi_mau_la_co_ngay_buoi_thu_va_phien_thu(to_chuc):
    tid, cls = to_chuc
    with tenant_scope(tid):
        cap = db.ensure_capture_session(
            tenant_id=tid, class_uid=cls, session_id="1787000000001",
            source_type="camera")

    assert cap is not None, "phải trả về capture_session_id ngay trong lượt ghi"
    assert _dem(tid, "collection_sessions") == 1
    assert _dem(tid, "capture_sessions") == 1

    with system_scope("test: doc lai"):
        row = db._fetch_all(
            "SELECT c.tenant_id, c.class_uid, c.session_id, c.signer_id, "
            "       s.session_code, s.tenant_id AS tenant_cha "
            "FROM capture_sessions c JOIN collection_sessions s "
            "  ON s.collection_session_id = c.collection_session_id "
            "WHERE c.capture_session_id = %s", (cap,))[0]

    assert row["tenant_id"] == tid and row["tenant_cha"] == tid
    assert row["class_uid"] == cls
    assert row["session_code"] == row["session_id"] == "1787000000001"
    # Người ký KHÔNG được suy ra ở tầng phiên — xem docstring của
    # `ensure_capture_session`. Bảng cha không còn cột người ký từ v6.
    assert row["signer_id"] is None


def test_thieu_du_kien_thi_tra_None_chu_khong_no(to_chuc):
    """Mẫu vẫn phải ghi được khi không có mã phiên. Không đánh đổi việc ghi mẫu
    lấy việc dựng phân cấp."""
    tid, cls = to_chuc
    with tenant_scope(tid):
        assert db.ensure_capture_session(
            tenant_id=tid, class_uid=cls, session_id="") is None
        assert db.ensure_capture_session(
            tenant_id=tid, class_uid="", session_id="x") is None
    assert _dem(tid, "collection_sessions") == 0


# --------------------------------------------------------------- dựng một lần

def test_goi_lai_dung_lai_dung_phien_khong_nhan_ban(to_chuc):
    """60 mẫu của một lớp trong một lượt ngồi quay = MỘT phiên, không phải 60.

    Đây cũng là phép kiểm chống nhân bản khi người dùng bấm lại sau lỗi mạng.
    """
    tid, cls = to_chuc
    with tenant_scope(tid):
        cac_id = {
            db.ensure_capture_session(
                tenant_id=tid, class_uid=cls, session_id="1787000000002")
            for _ in range(5)
        }
    assert len(cac_id) == 1, "gọi lại phải trả về đúng phiên cũ"
    assert _dem(tid, "capture_sessions") == 1
    assert _dem(tid, "collection_sessions") == 1


def test_cung_buoi_khac_lop_thi_chung_cha_nhung_khac_phien(to_chuc):
    """Một lượt ngồi quay đi qua nhiều nhãn — đúng hình dạng đã đo trên sản
    xuất: 57 mã phiên trải thành 250 capture session."""
    tid, cls = to_chuc
    cls2 = f"cls_{uuid.uuid4().hex[:8]}"
    with system_scope("test: them lop thu hai"):
        db._execute(
            "INSERT INTO classes(class_uid, tenant_id, slug, label_original, "
            "language, region, is_active) VALUES(%s,%s,'h','H','vn','common',true)",
            (cls2, tid))

    with tenant_scope(tid):
        a = db.ensure_capture_session(tenant_id=tid, class_uid=cls,
                                      session_id="1787000000003")
        b = db.ensure_capture_session(tenant_id=tid, class_uid=cls2,
                                      session_id="1787000000003")
    assert a != b
    assert _dem(tid, "capture_sessions") == 2
    assert _dem(tid, "collection_sessions") == 1, "cùng mã phiên = cùng một buổi"


def test_ma_phien_trung_nhau_giua_hai_to_chuc_khong_dinh_vao_nhau(to_chuc):
    """Mã phiên là epoch-ms của trình duyệt nên hai tổ chức đụng nhau được.

    Khoá tự nhiên là CẶP `(tenant_id, session_code)`, nên đụng độ mã không làm
    hai tổ chức dùng chung một buổi thu.
    """
    tid, cls = to_chuc
    tid2 = f"test-{uuid.uuid4().hex[:8]}"
    cls2 = f"cls_{uuid.uuid4().hex[:8]}"
    with system_scope("test: to chuc thu hai"):
        db._execute("INSERT INTO tenants(tenant_id, display_name, slug) VALUES(%s,%s,%s)",
                    (tid2, "Tổ chức khác", tid2))
        db._execute(
            "INSERT INTO classes(class_uid, tenant_id, slug, label_original, "
            "language, region, is_active) VALUES(%s,%s,'k','K','vn','common',true)",
            (cls2, tid2))
    try:
        ma = "1787000000004"
        with tenant_scope(tid):
            a = db.ensure_capture_session(tenant_id=tid, class_uid=cls, session_id=ma)
        with tenant_scope(tid2):
            b = db.ensure_capture_session(tenant_id=tid2, class_uid=cls2, session_id=ma)
        assert a != b
        assert _dem(tid, "collection_sessions") == 1
        assert _dem(tid2, "collection_sessions") == 1
    finally:
        from app.tenant_lifecycle import PURGE_ORDER

        with system_scope("test: don to chuc thu hai"):
            for bang in PURGE_ORDER:
                try:
                    db._execute(f"DELETE FROM {bang} WHERE tenant_id = %s", (tid2,))
                except Exception:
                    pass
            db._execute("DELETE FROM tenants WHERE tenant_id = %s", (tid2,))


# ------------------------------------------- mẫu mới không còn cần backfill

def test_mau_ghi_bang_duong_moi_khong_con_can_backfill(to_chuc):
    """Tiêu chí nghiệm thu quan trọng nhất.

    Chạy lại đúng hai câu backfill của migration sau khi đường ghi mới đã làm
    việc: chúng phải KHÔNG sinh thêm capture session nào, và KHÔNG phải sửa
    con trỏ nào. Nếu test này đỏ thì runtime vẫn đang để migration dọn hộ.
    """
    tid, cls = to_chuc
    with tenant_scope(tid):
        cap = db.ensure_capture_session(
            tenant_id=tid, class_uid=cls, session_id="1787000000005",
            source_type="camera")
        db.insert_sample({
            "sample_uid": uuid.uuid4().hex[:10],
            "class_uid": cls, "tenant_id": tid, "session_id": "1787000000005",
            "capture_session_id": cap, "seq_len": 60, "augment_id": 0,
            "file_path": "x.npz", "review_status": "pending",
        })

    truoc = _dem(tid, "capture_sessions")
    with system_scope("test: phat lai backfill cua migration"):
        db._execute(db._SQL_BACKFILL_COLLECTION_SESSIONS)
        db._execute(db._SQL_LINK_CAPTURE_TO_COLLECTION)
    assert _dem(tid, "capture_sessions") == truoc, \
        "backfill KHÔNG được sinh thêm phiên cho mẫu do đường ghi mới tạo"

    with system_scope("test: doc lai mau"):
        row = db._fetch_all(
            "SELECT capture_session_id FROM samples WHERE tenant_id = %s", (tid,))[0]
    assert str(row["capture_session_id"]) == str(cap), \
        "con trỏ của mẫu phải giữ nguyên, không bị backfill ghi đè"


def test_duong_thu_mau_that_su_goi_ham_dung_phan_cap(to_chuc):
    """Mắt xích cuối: hàm chạy đúng KHÔNG có nghĩa là đường ghi có gọi nó.

    Mọi test trên đây gọi thẳng `ensure_capture_session`. Bài này đi qua
    `save_sequence_npz` — điểm nghẽn mà cả bốn đường ghi mẫu (camera, video,
    dataset, oversample) đều đi qua — và bắt lấy dòng mà nó ĐỊNH ghi vào
    Postgres. Không có bài này, gỡ lời gọi ra khỏi `save_sequence_npz` vẫn xanh.

    Chặn ghi tệp và chặn `insert_sample`, nhưng KHÔNG chặn
    `ensure_capture_session`: buổi thu và phiên thu phải được dựng thật, vì thứ
    đang kiểm là chúng có ra đời trong cùng lượt ghi hay không.
    """
    import numpy as np
    from app import dataset_samples as ds
    from app.dataset_manager import ClassMetadata

    tid, cls = to_chuc
    bat: dict = {}
    goc_csv, goc_npz, goc_json = (
        ds.append_sample_row, ds._atomic_write_npz, ds.atomic_write_json)
    import app.storage.metadata_db as mdb
    goc_insert = mdb.insert_sample
    ds.append_sample_row = lambda row: None
    ds._atomic_write_npz = lambda *a, **k: None
    ds.atomic_write_json = lambda *a, **k: None
    mdb.insert_sample = lambda row: bat.update(db=dict(row))
    try:
        lop = ClassMetadata(
            class_uid=cls, class_idx=1, slug="g", label_original="G",
            language="vn", dialect="common", is_common_global=False,
            is_common_language=False, tenant_id=tid)
        with tenant_scope(tid):
            ds.save_sequence_npz(
                lop, np.zeros((60, 126), dtype=np.float32),
                meta={"session_id": "1787000000007"}, augment_id=0,
                source_type="camera")
    finally:
        ds.append_sample_row, ds._atomic_write_npz, ds.atomic_write_json = (
            goc_csv, goc_npz, goc_json)
        mdb.insert_sample = goc_insert

    row = bat.get("db")
    assert row is not None, "khong bat duoc dong Postgres nao"
    assert row.get("capture_session_id"), (
        "duong thu mau khong gan capture_session_id — mau se lai phai cho "
        "backfill cua migration nhu truoc 24/08/2026")
    assert _dem(tid, "collection_sessions") == 1
    assert _dem(tid, "capture_sessions") == 1


def test_dong_bo_csv_khong_xoa_con_tro_da_dung(to_chuc):
    """`samples.csv` không có cột `capture_session_id`, nên mọi dòng đến từ lượt
    đồng bộ đều IM LẶNG về nó. Không có COALESCE trong `SQL_UPSERT_SAMPLE`, mỗi
    lượt đồng bộ sẽ xoá con trỏ vừa dựng rồi lượt migrate sau lại dựng lại — một
    vòng lặp câm không ai thấy."""
    tid, cls = to_chuc
    uid = uuid.uuid4().hex[:10]
    with tenant_scope(tid):
        cap = db.ensure_capture_session(tenant_id=tid, class_uid=cls,
                                        session_id="1787000000006")
        db.insert_sample({"sample_uid": uid, "class_uid": cls, "tenant_id": tid,
                          "session_id": "1787000000006", "capture_session_id": cap,
                          "seq_len": 60, "augment_id": 0, "file_path": "x.npz"})
        # Lượt đồng bộ từ CSV: cùng sample_uid, KHÔNG có capture_session_id.
        db.insert_sample({"sample_uid": uid, "class_uid": cls, "tenant_id": tid,
                          "session_id": "1787000000006",
                          "seq_len": 60, "augment_id": 0, "file_path": "x.npz"})

    with system_scope("test: doc lai"):
        row = db._fetch_all("SELECT capture_session_id FROM samples WHERE sample_uid = %s",
                            (uid,))[0]
    assert str(row["capture_session_id"]) == str(cap)
