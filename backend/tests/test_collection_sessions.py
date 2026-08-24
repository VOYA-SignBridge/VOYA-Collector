"""Buổi thu: tầng cha bị nhét vào một cột chuỗi cho tới 23/08/2026.

`capture_sessions.session_id` là mã trình duyệt sinh ra. Đo trên sản xuất:
250 capture session nhưng chỉ 57 mã, và mỗi capture session đúng một lớp. Tức
là một buổi ngồi thu đẻ ra nhiều capture session, và tầng "buổi" chưa từng
tồn tại như một hàng — nó chỉ là một chuỗi lặp lại.

Hai điều các test này canh, và chúng khác nhau:

    cấu trúc   mọi capture session phải có cha, cha phải đúng nhóm
    lực học    người ký ở hai tầng KHÔNG được mâu thuẫn

Vế thứ hai là thứ biện minh cho việc nâng `signer_id` lên bảng cha. Dữ liệu
cho phép nâng (0/57 buổi có quá một người ký) — nhưng "dữ liệu hôm nay cho
phép" không phải là bảo đảm, và ràng buộc mới là bảo đảm.

Ngược lại `auth_user_id` KHÔNG được nâng, vì 1/57 buổi có hai tài khoản cùng
thu. Bảng cha chỉ giữ `opened_by_user_id` — ai mở buổi — và không có ràng
buộc nào bắt các capture session con phải cùng tài khoản, vì điều đó sai.

Chạy trên Postgres thật. Mọi test tự hoàn tác trong giao dịch của nó.
"""

from __future__ import annotations

import uuid

import psycopg2
import pytest

from app.storage import metadata_db as db


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def cur():
    """Cursor có phạm vi hệ thống, luôn hoàn tác.

    Phạm vi là bắt buộc chứ không phải tiện tay: `collection_sessions` chịu
    RLS, nên một kết nối không phạm vi sẽ ngã ở `WITH CHECK` TRƯỚC khi khoá
    ngoại được hỏi tới. Test vẫn đỏ-rồi-xanh, nhưng xanh vì lý do sai:
    `InsufficientPrivilege` thay cho `ForeignKeyViolation`, và ràng buộc đang
    được kiểm thì không hề chạy. Xem chú thích cùng nội dung ở
    `test_tenant_foreign_keys.rollback_cursor`.
    """
    from app.storage.rls import apply_scope
    from app.tenant_context import system_scope

    conn = psycopg2.connect(db.settings.database_url)
    conn.autocommit = False
    try:
        with system_scope("test: buoi thu xuyen tenant"):
            with conn.cursor() as c:
                apply_scope(c)
                yield c
    finally:
        conn.rollback()
        conn.close()


def _dung_buoi(cur, *, signers=()):
    """Một tenant + lớp + buổi thu dùng được, trả về (tenant, lớp, buổi).

    `signers` tạo sẵn các hàng `signers` cho tenant ấy. Chúng KHÔNG được gắn
    vào buổi thu: từ v6 `collection_sessions` không còn cột người ký.
    """
    tid = f"test-{uuid.uuid4().hex[:8]}"
    cur.execute("INSERT INTO tenants(tenant_id, display_name, slug) VALUES(%s,%s,%s)",
                (tid, "Thử buổi thu", tid))
    cls = f"cls_{uuid.uuid4().hex[:8]}"
    cur.execute(
        "INSERT INTO classes(class_uid, tenant_id, slug, label_original, language, "
        "region, is_active) VALUES(%s,%s,'b','B','vn','common',true)", (cls, tid))
    for sid in signers:
        cur.execute(
            "INSERT INTO signers(signer_id, display_name, tenant_id) VALUES(%s,%s,%s)",
            (sid, sid, tid))
    buoi = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO collection_sessions(collection_session_id, tenant_id, "
        "session_code) VALUES(%s,%s,%s)",
        (buoi, tid, f"code-{uuid.uuid4().hex[:6]}"))
    return tid, cls, buoi


# ------------------------------------------------------------------ cấu trúc

def test_moi_capture_session_tren_san_xuat_deu_co_buoi_cha(cur):
    """Hậu điều kiện của bước migration, kiểm lại như một bất biến sống.

    Bước backfill tự kiểm mình lúc chạy, nhưng nó chỉ chạy một lần. Đường ghi
    capture session mới mà quên gán buổi sẽ không làm bước ấy đỏ lại — nó làm
    test này đỏ.
    """
    cur.execute("SELECT count(*) FROM capture_sessions WHERE collection_session_id IS NULL")
    assert cur.fetchone()[0] == 0


def test_buoi_cha_phai_dung_tenant_va_dung_ma_phien(cur):
    """Vế hai của hậu điều kiện: đã nối KHÔNG đồng nghĩa nối đúng chỗ.

    Một bản vá gom mọi capture session vào một buổi duy nhất vẫn qua được
    phép kiểm "không còn mồ côi". Đây là phép kiểm phân biệt hai thứ đó.
    """
    cur.execute(
        "SELECT count(*) FROM capture_sessions c "
        "JOIN collection_sessions s USING (collection_session_id) "
        "WHERE s.tenant_id IS DISTINCT FROM c.tenant_id "
        "   OR s.session_code IS DISTINCT FROM c.session_id")
    assert cur.fetchone()[0] == 0


def test_mot_capture_session_van_chi_thu_mot_lop(cur):
    """Lý do `class_uid` được giữ ở capture session chứ không nâng lên buổi."""
    cur.execute(
        "SELECT count(*) FROM (SELECT capture_session_id FROM samples "
        "WHERE capture_session_id IS NOT NULL "
        "GROUP BY capture_session_id HAVING count(DISTINCT class_uid) > 1) x")
    assert cur.fetchone()[0] == 0


# ------------------------------------------------------------------ lực học

def test_capture_session_khong_gan_duoc_vao_buoi_cua_tenant_khac(cur):
    tid, cls, buoi = _dung_buoi(cur)
    khac = f"test-{uuid.uuid4().hex[:8]}"
    cur.execute("INSERT INTO tenants(tenant_id, display_name, slug) VALUES(%s,%s,%s)",
                (khac, "Tenant khác", khac))
    cur.execute(
        "INSERT INTO classes(class_uid, tenant_id, slug, label_original, language, "
        "region, is_active) VALUES(%s,%s,'k','K','vn','common',true)",
        (f"cls_{uuid.uuid4().hex[:8]}", khac))
    cur.execute("SELECT class_uid FROM classes WHERE tenant_id = %s", (khac,))
    cls_khac = cur.fetchone()[0]

    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute(
            "INSERT INTO capture_sessions(capture_session_id, tenant_id, class_uid, "
            "session_id, collection_session_id) VALUES(%s,%s,%s,'x',%s)",
            (str(uuid.uuid4()), khac, cls_khac, buoi))


def test_mot_buoi_thu_chua_duoc_HAI_nguoi_ky_khac_nhau(cur):
    """ĐỐI CHỨNG DƯƠNG của v6 — bài quan trọng nhất tệp này.

    Từ 23 đến 24/08/2026 lược đồ có `collection_sessions.signer_id` cùng một
    khoá ngoại ghép ba cột bắt người ký của capture session phải TRÙNG người ký
    của buổi. Chính bài test này, ở phiên bản trước, ghim bất biến ấy lại.

    Nó sai. Đo bằng nhãn thô trên sản xuất: 10/253 capture session chứa từ hai
    nhãn người ký trở lên — hai người thay phiên ký cùng một từ trong một lượt
    quay. Buổi `1784530308361` mang `signer_id = 'S011'` trong khi chứa Khoa,
    Minh và Trân.

    Nên phép khẳng định bị ĐẢO CHIỀU: điều trước kia phải bị từ chối thì nay
    phải chạy được. Chừng nào bài này còn xanh, v6 còn thật sự đã gỡ bất biến
    sai chứ không chỉ bỏ một cột.
    """
    tid, cls, buoi = _dung_buoi(cur, signers=("S900", "S901"))
    cls2 = f"cls_{uuid.uuid4().hex[:8]}"
    cur.execute(
        "INSERT INTO classes(class_uid, tenant_id, slug, label_original, language, "
        "region, is_active) VALUES(%s,%s,'b2','B2','vn','common',true)", (cls2, tid))

    for lop, nguoi_ky in ((cls, "S900"), (cls2, "S901")):
        cur.execute(
            "INSERT INTO capture_sessions(capture_session_id, tenant_id, class_uid, "
            "session_id, collection_session_id, signer_id) VALUES(%s,%s,%s,%s,%s,%s)",
            (str(uuid.uuid4()), tid, lop, f"s-{lop[-4:]}", buoi, nguoi_ky))

    cur.execute(
        "SELECT count(DISTINCT signer_id) FROM capture_sessions "
        "WHERE collection_session_id = %s", (buoi,))
    assert cur.fetchone()[0] == 2, "một buổi thu phải chứa được hai người ký"


def test_nguoi_ky_van_phai_thuoc_dung_tenant(cur):
    """v6 gỡ bất biến SAI, không gỡ cách ly tenant.

    Không có bài này, một bản vá "gỡ hết ràng buộc người ký cho xong" cũng
    xanh ở bài trên.
    """
    tid, cls, buoi = _dung_buoi(cur, signers=("S900",))
    khac = f"test-{uuid.uuid4().hex[:8]}"
    cur.execute("INSERT INTO tenants(tenant_id, display_name, slug) VALUES(%s,%s,%s)",
                (khac, "Tenant khác", khac))
    cur.execute("INSERT INTO signers(signer_id, display_name, tenant_id) "
                "VALUES('S999','S999',%s)", (khac,))

    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute(
            "INSERT INTO capture_sessions(capture_session_id, tenant_id, class_uid, "
            "session_id, collection_session_id, signer_id) VALUES(%s,%s,%s,'x',%s,'S999')",
            (str(uuid.uuid4()), tid, cls, buoi))


def test_capture_session_chua_biet_nguoi_ky_thi_van_gan_duoc(cur):
    """2186/3864 mẫu chưa có người ký. Chưa biết thì để NULL — và NULL phải đi
    qua được, nếu không thì đúng phần dữ liệu đang cần nối lại bị chặn."""
    tid, cls, buoi = _dung_buoi(cur, signers=("S900",))
    cur.execute(
        "INSERT INTO capture_sessions(capture_session_id, tenant_id, class_uid, "
        "session_id, collection_session_id, signer_id) VALUES(%s,%s,%s,'x',%s,NULL)",
        (str(uuid.uuid4()), tid, cls, buoi))
    cur.execute("SELECT count(*) FROM capture_sessions WHERE collection_session_id = %s",
                (buoi,))
    assert cur.fetchone()[0] == 1


def test_buoi_thu_khong_con_cot_nguoi_ky(cur):
    """Hậu điều kiện v6, kiểm như một bất biến sống.

    Một lượt sửa sau này thêm lại cột ấy — kèm ràng buộc khớp — sẽ tái lập
    đúng lỗi v6 sinh ra để gỡ. Bài này bắt được việc đó.
    """
    cur.execute(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = 'collection_sessions' AND column_name = 'signer_id'")
    assert cur.fetchone()[0] == 0
    cur.execute(
        "SELECT count(*) FROM pg_constraint "
        "WHERE conname IN ('fk_capture_sessions_collection_signer', "
        "                  'uq_collection_sessions_signer_scope')")
    assert cur.fetchone()[0] == 0


def test_xoa_buoi_thu_chi_go_con_tro_chu_khong_hong(cur):
    """`SET NULL (collection_session_id)` — danh sách cột, không phải SET NULL trần.

    SET NULL trần sẽ đặt NULL cho cả `tenant_id`, vốn NOT NULL, nên xoá một
    buổi thu sẽ nổ thay vì gỡ con trỏ.
    """
    tid, cls, buoi = _dung_buoi(cur)
    cs = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO capture_sessions(capture_session_id, tenant_id, class_uid, "
        "session_id, collection_session_id) VALUES(%s,%s,%s,'x',%s)", (cs, tid, cls, buoi))
    cur.execute("DELETE FROM collection_sessions WHERE collection_session_id = %s", (buoi,))
    cur.execute("SELECT tenant_id, collection_session_id FROM capture_sessions "
                "WHERE capture_session_id = %s", (cs,))
    tenant_con_lai, con_tro = cur.fetchone()
    assert con_tro is None
    assert tenant_con_lai == tid


# ------------------------------------------------- ba sổ đăng ký phải khớp

#: Hai ngoại lệ, cả hai đều có lý do đã ghi ở nơi khai báo:
#:
#:   users  có `tenant_id` nhưng KHÔNG bị xoá theo tenant — xoá tổ chức không
#:          xoá con người
#:   roles  bị xoá theo tenant nhưng không nằm trong `TENANT_SCOPED_TABLES`,
#:          vì khoá ngoại tenant của nó được khai tường minh với CASCADE thay
#:          vì nhận RESTRICT từ vòng lặp chung
_NGOAI_LE_PURGE = {"users"}
_NGOAI_LE_SCOPED = {"roles"}


def test_bang_co_tenant_id_phai_co_mat_o_ca_ba_so_dang_ky():
    """Thêm một bảng tenant-scoped là BA việc, không phải một.

    Quên `RLS_TABLES` thì bảng mới đọc được xuyên tổ chức. Quên `PURGE_ORDER`
    thì lượt xoá tenant dừng giữa chừng ở khoá ngoại RESTRICT mà chính vòng
    lặp chung vừa cấp cho nó — và dừng giữa chừng nghĩa là tổ chức đã mất một
    phần dữ liệu nhưng vẫn còn tồn tại.

    Test này biến danh sách kiểm ấy thành thứ máy nhớ hộ.
    """
    from app.storage.rls import RLS_TABLES
    from app.tenant_lifecycle import PURGE_ORDER

    scoped = set(db.TENANT_SCOPED_TABLES)
    assert scoped - set(RLS_TABLES) == set(), "bảng tenant-scoped thiếu policy RLS"
    assert scoped - set(PURGE_ORDER) == _NGOAI_LE_PURGE, "bảng tenant-scoped thiếu ở PURGE_ORDER"
    assert set(PURGE_ORDER) - scoped == _NGOAI_LE_SCOPED


def test_vai_ung_dung_voi_toi_duoc_moi_bang_tenant_scoped(cur):
    """Việc thứ TƯ khi thêm một bảng có `tenant_id`, và là việc dễ quên nhất.

    Ba việc kia — `TENANT_SCOPED_TABLES`, `RLS_TABLES`, `PURGE_ORDER` — đều
    nằm trong mã và thấy được khi đọc diff. Việc thứ tư nằm ở CƠ SỞ DỮ LIỆU:
    vai ứng dụng phải được CẤP QUYỀN trên bảng mới.

    Nó im lặng theo cách tệ nhất. `ALTER DEFAULT PRIVILEGES` chỉ áp cho bảng do
    ĐÚNG vai đã chạy câu ấy tạo ra, nên một bảng sinh ra bởi vai khác lọt lưới.
    Và bộ test không bắt được, vì test chạy bằng một vai có nhiều quyền hơn vai
    sản xuất — đúng kiểu "xanh vì đo bằng dụng cụ sai".

    Đo ngày 24/08/2026 trên `signdb_test`: bốn bảng mà `voya_app` không đọc nổi
    (`collection_sessions`, `project_allocations`, `regions`, `tenant_purges`).
    Hậu quả không dừng ở bảng ấy: `purge_tenant` chạy dưới vai ứng dụng nuốt
    lỗi quyền, tenant không xoá được, rác dồn lại, và cuối cùng làm ĐỎ một test
    chẳng liên quan gì — bất biến "mọi tổ chức đang sống đều có đăng ký đang
    mở" của bộ đọc SOT.

    `regions` chỉ cần SELECT: nó là danh mục tham chiếu, quyền ghi bị thu có
    chủ đích (xem `REFERENCE_TABLES` trong `provision_db_roles`).
    """
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'voya_app'")
    if cur.fetchone() is None:
        pytest.skip("cơ sở dữ liệu này không có vai ứng dụng")

    cur.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' "
        "  AND c.relname = ANY(%s) "
        "  AND NOT has_table_privilege('voya_app', c.oid, 'SELECT') "
        "ORDER BY 1",
        (list(db.TENANT_SCOPED_TABLES),))
    thieu = [r[0] for r in cur.fetchall()]
    assert thieu == [], f"vai ứng dụng không đọc được: {', '.join(thieu)}"


def test_buoi_thu_bi_xoa_truoc_khi_xoa_nguoi_ky():
    """Thứ tự trong `PURGE_ORDER` là một phần của tính đúng, không phải thẩm mỹ."""
    from app.tenant_lifecycle import PURGE_ORDER

    thu_tu = list(PURGE_ORDER)
    assert thu_tu.index("capture_sessions") < thu_tu.index("collection_sessions"), \
        "capture session trỏ LÊN buổi thu, nên phải bị xoá trước"
    assert thu_tu.index("collection_sessions") < thu_tu.index("signers"), \
        "buổi thu trỏ XUỐNG người ký, nên phải bị xoá trước signers"
