"""Quota dung lượng: hạn mức dữ liệu duy nhất từ v8.

Tệp này canh ba lớp của `app/storage_quota.py`, và mỗi lớp hỏng theo một kiểu
riêng nên mỗi lớp có bài riêng:

    bộ đếm bền          cộng đúng, trừ đúng, không âm
    chặn đồng bộ        dưới trần thì ghi được, vượt trần thì chặn — NGAY lúc ghi
    đối chiếu           bộ đếm cố tình làm lệch phải được sửa và phải KÊU

Hai bài quan trọng nhất:

`test_sau_luot_ghi_dong_thoi_chi_ba_luot_qua`
    Đọc-rồi-kiểm-rồi-ghi trông đúng trong mọi bài tuần tự và sai trong sản xuất.

`test_quyet_toan_vuot_tran_thi_go_hien_vat_va_tu_choi`
    Nếu bài này hỏng thì hạn mức chỉ là một phép kiểm TRƯỚC lượt tải, không phải
    một trần: một ước lượng sai về phía thấp sẽ để tệp nằm lại trên đĩa ngoài
    hạn mức.
"""

from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path

import pytest

from app import storage_quota as sq
from app.storage import metadata_db as db
from app.tenant_context import system_scope, tenant_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def to_chuc():
    """Tenant thật, gói Free (2 GB), dọn sạch cả DB lẫn ĐĨA sau bài."""
    from app import tenant_admin
    from app.dataset_manager import tenant_features_root
    from conftest import purge_tenant

    tid = f"stq{uuid.uuid4().hex[:9]}"
    tenant_admin.create_tenant(tid, clone_catalog=False, plan_code="free")
    try:
        yield tid
    finally:
        with system_scope("test: don bo dem va so giu cho"):
            db._execute("DELETE FROM storage_reservations WHERE tenant_id = %s", (tid,))
            db._execute("DELETE FROM tenant_storage WHERE tenant_id = %s", (tid,))
        # Bản sao Postgres không che được đường ghi TỆP: các bài đối chiếu ở
        # dưới tạo tệp thật dưới gốc của tenant này, và không dọn thì chúng ở
        # lại trong dataset thật.
        shutil.rmtree(tenant_features_root(tid), ignore_errors=True)
        purge_tenant(tid)


def _dat_bo_dem(tid: str, n: int) -> None:
    with system_scope("test: dat bo dem"):
        db._execute("INSERT INTO tenant_storage(tenant_id, bytes_used) VALUES(%s,%s) "
                    "ON CONFLICT (tenant_id) DO UPDATE SET bytes_used = EXCLUDED.bytes_used",
                    (tid, n))


def _tran(tid: str) -> int:
    from app.plans import plan_for_tenant
    return int(plan_for_tenant(tid)["max_storage_mb"]) * 1024 * 1024


def _so_khoan_giu_cho(tid: str) -> int:
    with system_scope("test: dem so dong so giu cho"):
        rows = db._fetch_all(
            "SELECT count(*) AS n FROM storage_reservations WHERE tenant_id = %s", (tid,))
    return int(rows[0]["n"])


def _ghi_tep(tid: str, ten: str, n: int) -> Path:
    """Ghi `n` byte vào cây đặc trưng của tenant — hiện vật TÍNH PHÍ thật."""
    from app.dataset_manager import tenant_features_root

    p = tenant_features_root(tid) / "vn" / "common" / "class_test_0000" / ten
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\0" * n)
    return p


# ------------------------------------------------------- sổ giữ chỗ

def test_giu_cho_khong_dong_vao_bo_dem_da_dung(to_chuc):
    """Phân biệt trung tâm của v8: giữ chỗ là LỜI HỨA, không phải byte trên đĩa.

    Nếu `reserve` cộng thẳng vào `bytes_used` thì lượt đối chiếu — vốn đo đĩa —
    sẽ xoá khoản ấy đi ở lần chạy sau, và một tiến trình chết sẽ để lại một
    khoản dùng vĩnh viễn cho dữ liệu chưa từng tồn tại.
    """
    giu = sq.reserve(to_chuc, 1000)
    assert sq.bytes_used(to_chuc) == 0, "giữ chỗ KHÔNG được tính là đã dùng"
    assert sq.bytes_reserved(to_chuc) == 1000
    sq.release(giu)
    assert sq.bytes_reserved(to_chuc) == 0


def test_phep_nhan_viec_cong_ca_phan_dang_giu_cho(to_chuc):
    """Trần phải tính cả các lượt ghi đang bay, không chỉ phần đã hạ cánh."""
    tran = _tran(to_chuc)
    sq.reserve(to_chuc, tran - 1024)                # chưa chạm đĩa byte nào
    assert sq.bytes_used(to_chuc) == 0
    sq.reserve(to_chuc, 1024)                       # vừa khít
    with pytest.raises(sq.StorageQuotaExceeded):
        sq.reserve(to_chuc, 1)


def test_tra_lai_hai_lan_la_vo_hai(to_chuc):
    giu = sq.reserve(to_chuc, 500)
    sq.release(giu)
    sq.release(giu)                                 # dòng đã xoá, khớp 0 hàng
    assert sq.bytes_reserved(to_chuc) == 0


def test_sai_pham_vi_tenant_KHONG_duoc_bao_la_het_dung_luong(to_chuc):
    """Đối chứng cho một lỗi đã xảy ra thật.

    Không đọc được hàng có hai nguyên nhân, và gộp chúng làm một khiến một lỗi
    phạm vi hiện ra với người dùng dưới dạng "hết dung lượng" — sau đó không ai
    đi tìm đúng chỗ nữa. Đo được lần đầu ở bài đua dưới đây: 0/6 qua thay vì 3/6.

    Dựng lại bằng một phạm vi SAI chứ không phải một tenant không tồn tại: tenant
    không tồn tại thì đụng khoá ngoại, một lỗi khác hẳn. Ở đây hàng có thật và
    RLS che nó đi — đúng hình dạng của lỗi thật. (Cả suite chạy dưới
    `system_scope`; vào một `tenant_scope` sẽ rời phạm vi hệ thống.)
    """
    khac = f"stq{uuid.uuid4().hex[:9]}"
    sq.reserve(to_chuc, 10)                          # hàng tồn tại, và nhìn thấy được
    with tenant_scope(khac):                         # ...nhưng không phải từ đây
        with pytest.raises(sq.StorageScopeMissing):
            sq.reserve(to_chuc, 10)


# ----------------------------------------------------------- quyết toán

def test_quyet_toan_dung_bang_giu_cho(to_chuc):
    giu = sq.reserve(to_chuc, 1000)
    sq.settle(giu, 1000, absorb_overflow=True)
    assert sq.bytes_used(to_chuc) == 1000
    assert sq.bytes_reserved(to_chuc) == 0, "khoản giữ chỗ phải được tiêu"


def test_quyet_toan_it_hon_thi_tra_lai_phan_thua(to_chuc):
    giu = sq.reserve(to_chuc, 5000)
    sq.settle(giu, 1200, absorb_overflow=True)
    assert sq.bytes_used(to_chuc) == 1200
    assert sq.bytes_reserved(to_chuc) == 0


def test_quyet_toan_nhieu_hon_ma_CON_CHO_thi_nhan_binh_thuong(to_chuc):
    """Ước lượng thấp nhưng vẫn vừa trần — không có gì phải từ chối."""
    giu = sq.reserve(to_chuc, 1000)
    sq.settle(giu, 1500, discard=lambda: pytest.fail("khong duoc go gi khi con cho"))
    assert sq.bytes_used(to_chuc) == 1500


def test_quyet_toan_vuot_tran_thi_go_hien_vat_va_tu_choi(to_chuc):
    """Bài giữ cho hạn mức là một TRẦN chứ không phải một phép kiểm trước tải.

    Dựng đúng tình huống của đề bài: giữ chỗ 8 phần, tệp thật 11 phần, chỉ còn 1
    phần trống. Cộng thẳng 11 vào bộ đếm là chấp nhận rằng trần đã bị vượt SAU
    KHI tệp tồn tại.
    """
    phan = 1024 * 1024
    _dat_bo_dem(to_chuc, _tran(to_chuc) - 9 * phan)   # còn 9 phần
    giu = sq.reserve(to_chuc, 8 * phan)
    truoc = sq.bytes_used(to_chuc)

    tep = _ghi_tep(to_chuc, "sample_qua_to.npz", 4096)
    assert tep.is_file()

    with pytest.raises(sq.StorageQuotaExceeded) as bat:
        sq.settle(giu, 11 * phan, discard=lambda: tep.unlink())

    assert not tep.exists(), "hiện vật vừa ghi phải bị gỡ"
    assert sq.bytes_used(to_chuc) == truoc, "không được tính phần đã bị từ chối"
    assert sq.bytes_reserved(to_chuc) == 0, "khoản giữ chỗ phải được trả"
    assert _so_khoan_giu_cho(to_chuc) == 0, "không được để lại dòng nào trong sổ"
    assert bat.value.code == "storage_full"
    assert bat.value.status_code == 402


def test_quyet_toan_vuot_tran_KHONG_cong_cac_khoan_giu_cho_khac(to_chuc):
    """Đối chứng có chủ ý cho một lựa chọn thiết kế.

    Byte của lượt này đã có thật; byte của người khác thì chưa. Nếu phép kiểm
    lúc quyết toán cộng cả các khoản đang bay, một lượt ghi vừa vặn sẽ bị từ
    chối chỉ vì có người tải cùng lúc — một lỗi phụ thuộc lưu lượng, không tái
    hiện được, và người dùng không hiểu nổi.
    """
    phan = 1024 * 1024
    _dat_bo_dem(to_chuc, _tran(to_chuc) - 10 * phan)
    cua_toi = sq.reserve(to_chuc, 4 * phan)
    sq.reserve(to_chuc, 6 * phan)                    # người khác, vẫn đang bay

    # 4 phần vừa khít phần trần còn lại nếu KHÔNG cộng khoản của người kia.
    sq.settle(cua_toi, 4 * phan,
              discard=lambda: pytest.fail("khong duoc tu choi vi luu luong cua nguoi khac"))
    assert sq.bytes_used(to_chuc) == _tran(to_chuc) - 6 * phan


def test_phai_neu_ro_cach_xu_ly_khi_vuot(to_chuc):
    """Không có mặc định. Im lặng chọn hộ ở đây chính là chỗ hạn mức thôi không
    còn là hạn mức."""
    giu = sq.reserve(to_chuc, 10)
    with pytest.raises(TypeError):
        sq.settle(giu, 10)
    with pytest.raises(TypeError):
        sq.settle(giu, 10, discard=lambda: None, absorb_overflow=True)


def test_mien_tru_billing_thi_khong_co_tran(to_chuc):
    """Tenant nền tảng giữ dữ liệu thật và không được một hạn mức thương mại
    chặn giữa chừng."""
    with system_scope("test: mien tru"):
        db._execute("UPDATE tenants SET billing_exempt = TRUE WHERE tenant_id = %s",
                    (to_chuc,))
    from app.plans import _clear_caches
    _clear_caches()
    _dat_bo_dem(to_chuc, _tran(to_chuc) * 10)
    giu = sq.reserve(to_chuc, 10 * 1024 * 1024 * 1024)
    sq.settle(giu, 10 * 1024 * 1024 * 1024, absorb_overflow=True)


# ------------------------------------------------- khoản giữ chỗ treo

def test_khoan_qua_han_khong_con_giam_cho(to_chuc):
    """Câu trả lời cho "tiến trình chết giữa reserve và settle".

    Không có nó thì một lần backend bị giết giữa lượt tải sẽ giam chỗ của tổ
    chức cho tới ngày hôm sau — và người dùng thấy "hết dung lượng" cho phần họ
    chưa hề ghi.
    """
    tran = _tran(to_chuc)
    sq.reserve(to_chuc, tran)                        # chiếm trọn trần
    with pytest.raises(sq.StorageQuotaExceeded):
        sq.reserve(to_chuc, 1)

    # Tiến trình chết: khoản ở lại, quá hạn.
    with system_scope("test: lam khoan giu cho qua han"):
        db._execute("UPDATE storage_reservations SET expires_at = NOW() - INTERVAL '1 minute' "
                    " WHERE tenant_id = %s", (to_chuc,))

    assert sq.bytes_reserved(to_chuc) == 0, "khoản quá hạn không được tính là đang giữ"
    sq.reserve(to_chuc, 1)                           # không ném là toàn bộ nội dung


def test_luot_quet_don_dung_khoan_qua_han(to_chuc):
    con_han = sq.reserve(to_chuc, 100)
    sq.reserve(to_chuc, 200)
    with system_scope("test: lam MOT khoan qua han"):
        db._execute("UPDATE storage_reservations SET expires_at = NOW() - INTERVAL '1 minute' "
                    " WHERE tenant_id = %s AND bytes = 200", (to_chuc,))

    sq.sweep_expired()
    assert _so_khoan_giu_cho(to_chuc) == 1, "chỉ khoản quá hạn được dọn"
    assert sq.bytes_reserved(to_chuc) == 100
    sq.release(con_han)


# ---------------------------------------------------------- cuộc đua

def test_sau_luot_ghi_dong_thoi_chi_ba_luot_qua(to_chuc):
    """Bài trung tâm của cả module.

    Đọc-rồi-kiểm-rồi-ghi cho kết quả ĐÚNG trong mọi bài tuần tự và SAI trong sản
    xuất: hai lượt cùng đọc "còn chỗ", cùng kết luận "được", cùng ghi.

    Ở đây trần còn đúng 3 phần; sáu luồng cùng xin một phần. Đếm số ngoại lệ
    thôi thì chưa đủ — một bản cài hỏng vẫn có thể ném đúng ba lần mà vẫn để lại
    rác trong sổ. Nên bài này kiểm cả HẬU QUẢ: sổ giữ đúng ba dòng, tổng đúng ba
    phần, và tổng cộng không vượt trần.
    """
    phan = 4 * 1024 * 1024
    tran = _tran(to_chuc)
    _dat_bo_dem(to_chuc, tran - 3 * phan)

    qua, chan, la = [], [], []
    rao = threading.Barrier(6)

    def mot_luot():
        # Phạm vi tenant phải đặt TRONG luồng: nó là `contextvar`, và luồng con
        # KHÔNG thừa kế. Thiếu nó thì RLS chặn mọi câu và bài test đo nhầm một
        # lỗi phạm vi thành "hết dung lượng" — đúng chuyện đã xảy ra ở bản đầu
        # của bài này (0/6 qua thay vì 3/6). Trong sản xuất phạm vi do middleware
        # đặt cho mỗi request.
        rao.wait()                      # cùng xuất phát, để cuộc đua là thật
        try:
            with tenant_scope(to_chuc):
                sq.reserve(to_chuc, phan)
            qua.append(1)
        except sq.StorageQuotaExceeded:
            chan.append(1)
        except Exception as exc:        # noqa: BLE001
            la.append(exc)

    luong = [threading.Thread(target=mot_luot) for _ in range(6)]
    for t in luong:
        t.start()
    for t in luong:
        t.join(timeout=30)

    assert not la, f"loi ngoai du kien: {la[:2]}"
    assert len(qua) == 3, f"phải đúng 3 lượt qua, thực tế {len(qua)}"
    assert len(chan) == 3
    # Hậu quả, không chỉ số ngoại lệ: ba luồng bị chặn không được để lại gì.
    assert _so_khoan_giu_cho(to_chuc) == 3, "sổ phải giữ đúng ba dòng"
    assert sq.bytes_reserved(to_chuc) == 3 * phan
    assert sq.bytes_used(to_chuc) + sq.bytes_reserved(to_chuc) <= tran


def test_bo_dem_cua_hai_to_chuc_khong_dinh_vao_nhau(to_chuc):
    from app import tenant_admin
    from conftest import purge_tenant

    khac = f"stq{uuid.uuid4().hex[:9]}"
    tenant_admin.create_tenant(khac, clone_catalog=False, plan_code="free")
    try:
        a = sq.reserve(to_chuc, 5000)
        b = sq.reserve(khac, 700)
        sq.settle(a, 5000, absorb_overflow=True)
        sq.settle(b, 700, absorb_overflow=True)
        assert sq.bytes_used(to_chuc) == 5000
        assert sq.bytes_used(khac) == 700
    finally:
        with system_scope("test: don tenant thu hai"):
            db._execute("DELETE FROM storage_reservations WHERE tenant_id = %s", (khac,))
            db._execute("DELETE FROM tenant_storage WHERE tenant_id = %s", (khac,))
        purge_tenant(khac)


# -------------------------------------------------------------- đối chiếu

def test_doi_chieu_sua_bo_dem_KHAI_THUA(to_chuc, caplog):
    import logging

    _ghi_tep(to_chuc, "sample_aaaaaaaaaa.npz", 3000)
    _dat_bo_dem(to_chuc, 999_999_999)
    with caplog.at_level(logging.WARNING):
        ket = sq.reconcile(to_chuc)

    assert ket["lech"] == 1
    assert sq.bytes_used(to_chuc) == 3000, "phải ghi đè theo số trên đĩa"
    assert any("bo dem lech" in r.getMessage() for r in caplog.records), \
        "lệch mà không KÊU thì bộ đếm trôi âm thầm"


def test_doi_chieu_sua_bo_dem_KHAI_THIEU(to_chuc, caplog):
    """Chiều còn lại. Một bộ đếm khai thiếu là hỏng theo hướng MỞ — tổ chức ghi
    được nhiều hơn phần đã mua, và không phép kiểm nào phản đối."""
    import logging

    _ghi_tep(to_chuc, "sample_bbbbbbbbbb.npz", 7000)
    _dat_bo_dem(to_chuc, 0)
    with caplog.at_level(logging.WARNING):
        ket = sq.reconcile(to_chuc)

    assert ket["lech"] == 1
    assert sq.bytes_used(to_chuc) == 7000
    assert any("bo dem lech" in r.getMessage() for r in caplog.records)


def test_doi_chieu_khong_keu_khi_khong_lech(to_chuc, caplog):
    """Đối chứng: nếu nó kêu cả khi đúng thì cảnh báo mất hết giá trị."""
    import logging

    _ghi_tep(to_chuc, "sample_cccccccccc.npz", 1500)
    sq.reconcile(to_chuc)                   # lần một: đưa bộ đếm về đúng
    # `at_level` chỉ đổi NGƯỠNG; `caplog.records` gom cả lượt chạy trước đó
    # trong cùng một pha. Không xoá thì bài này bắt được chính cảnh báo hợp lệ
    # của lần một và báo đỏ oan.
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ket = sq.reconcile(to_chuc)         # lần hai: phải im
    assert ket["lech"] == 0
    assert not any("bo dem lech" in r.getMessage() for r in caplog.records)


def test_doi_chieu_dem_ca_KHO_RAW_khong_chi_dac_trung(to_chuc):
    """Một mẫu là hai tệp ở hai cây. Bỏ kho raw ra là tính thiếu ~1/3 mỗi mẫu —
    và nó là nửa KHÔNG tái tạo được, tức nửa đắt hơn."""
    from app.dataset_samples import raw_archive_path

    dac_trung = _ghi_tep(to_chuc, "sample_dddddddddd.npz", 2000)
    kho = raw_archive_path(dac_trung)
    kho.parent.mkdir(parents=True, exist_ok=True)
    kho.write_bytes(b"\0" * 900)
    try:
        sq.reconcile(to_chuc)
        assert sq.bytes_used(to_chuc) == 2900, "kho raw phải được tính"
    finally:
        shutil.rmtree(kho.parents[3], ignore_errors=True)


def test_doi_chieu_KHONG_xoa_gi_khi_to_chuc_dang_vuot_tran(to_chuc, caplog):
    """Vượt trần sau khi HẠ GÓI là trạng thái nghiệp vụ hợp lệ.

    Lượt đối chiếu là kiểm toán: nó ghi nhận và báo, nhưng không xoá dữ liệu,
    không đổi gói, và không coi đây là hỏng dữ liệu. Cưỡng chế chỉ chặn lượt ghi
    TIẾP THEO — thứ đã có là của họ.
    """
    import logging

    tep = _ghi_tep(to_chuc, "sample_eeeeeeeeee.npz", 4096)
    with system_scope("test: ha goi xuong mot tran rat nho"):
        db._execute("UPDATE plans SET max_storage_mb = 0 WHERE plan_code = 'free'")
    from app.plans import _clear_caches
    _clear_caches()
    try:
        with caplog.at_level(logging.WARNING):
            ket = sq.reconcile(to_chuc)

        assert ket["vuot_tran"] == 1
        assert tep.is_file(), "đối chiếu KHÔNG được xoá dữ liệu của tổ chức"
        assert sq.bytes_used(to_chuc) == 4096, "vẫn phải ghi nhận đúng số thật"
        assert not any(r.levelno >= logging.WARNING and "vuot tran" in r.getMessage()
                       for r in caplog.records), \
            "vượt trần là trạng thái nghiệp vụ, không phải cảnh báo hằng ngày"
        # Và cưỡng chế thì vẫn chặn lượt ghi tiếp theo.
        with pytest.raises(sq.StorageQuotaExceeded):
            sq.reserve(to_chuc, 1)
    finally:
        with system_scope("test: tra goi free ve cu"):
            db._execute("UPDATE plans SET max_storage_mb = 2048 WHERE plan_code = 'free'")
        _clear_caches()


def test_doi_chieu_van_do_tenant_mien_tru(to_chuc):
    """Miễn trừ nghĩa là "không dùng trần để chặn", KHÔNG phải "không đo".

    Một tenant nền tảng không quan sát được là một tenant không ai biết đang
    chiếm bao nhiêu đĩa.
    """
    with system_scope("test: mien tru"):
        db._execute("UPDATE tenants SET billing_exempt = TRUE WHERE tenant_id = %s",
                    (to_chuc,))
    from app.plans import _clear_caches
    _clear_caches()

    _ghi_tep(to_chuc, "sample_ffffffffff.npz", 5555)
    sq.reconcile(to_chuc)
    assert sq.bytes_used(to_chuc) == 5555


# ------------------------------------------------ thử lại và xoá

def test_thu_lai_KHONG_tinh_hai_lan(to_chuc):
    """Một lượt tải bị hết giờ phía client rồi gửi lại phải tính MỘT lần.

    Ở đường HTTP, cổng chống trùng là `upload_uid`: lượt thứ hai trả về bản ghi
    cũ và thoát TRƯỚC khi giữ chỗ (thứ tự ấy là chủ ý — xem `upload_video`). Ở
    mức module, tính chất tương ứng là: một khoản giữ chỗ chỉ tiêu được MỘT lần.
    """
    giu = sq.reserve(to_chuc, 4096)
    sq.settle(giu, 4096, absorb_overflow=True)
    assert sq.bytes_used(to_chuc) == 4096

    # Cùng khoản ấy, lần thứ hai. Dòng trong sổ đã bị xoá, nên không được cộng
    # thêm gì nữa.
    sq.settle(giu, 4096, absorb_overflow=True)
    assert sq.bytes_used(to_chuc) == 4096, "quyết toán lại một khoản đã tiêu KHÔNG được cộng lần nữa"


def test_go_tep_thi_tra_lai_dung_so_byte(to_chuc):
    tep = _ghi_tep(to_chuc, "sample_1111111111.npz", 8000)
    sq.reconcile(to_chuc)
    assert sq.bytes_used(to_chuc) == 8000

    kich_thuoc = tep.stat().st_size
    tep.unlink()
    sq.uncharge(to_chuc, kich_thuoc)
    assert sq.bytes_used(to_chuc) == 0

    # Và lượt đối chiếu đồng ý — tức là bộ đếm và đĩa kể CÙNG một câu chuyện.
    sq.reconcile(to_chuc)
    assert sq.bytes_used(to_chuc) == 0


def test_tru_hai_lan_khong_lam_bo_dem_am(to_chuc):
    """Số âm làm MỌI phép kiểm sau đó đi qua — hỏng theo hướng MỞ."""
    _dat_bo_dem(to_chuc, 500)
    sq.uncharge(to_chuc, 500)
    sq.uncharge(to_chuc, 500)
    assert sq.bytes_used(to_chuc) == 0


def test_xoa_MEM_khong_duoc_tra_lai_dung_luong(to_chuc):
    """Xoá mềm giữ tệp lại (tệp đi khi Thùng rác được dọn), nên byte vẫn chiếm
    đĩa. Trả lại dung lượng ở lượt xoá mềm là tặng không chỗ cho dữ liệu vẫn
    đang nằm đó — và lượt đối chiếu sẽ lấy lại ngay hôm sau, làm con số nhảy qua
    nhảy lại mà người dùng không hiểu vì sao."""
    _ghi_tep(to_chuc, "sample_2222222222.npz", 6000)
    sq.reconcile(to_chuc)
    assert sq.bytes_used(to_chuc) == 6000

    # Đối chiếu lại khi tệp VẪN còn: con số phải đứng yên.
    sq.reconcile(to_chuc)
    assert sq.bytes_used(to_chuc) == 6000
