"""Chưa biết người ký thì để NULL — không bịa ra một thực thể để khoá ngoại vui.

Vết đã đo
---------
Ngày 08/08/2026 một câu backfill tạo hàng `signers` cho mọi `signer_id` mà
`samples` tham chiếu nhưng chưa có dòng. Lý lẽ nghe xuôi: "gỡ tham chiếu là mất
thông tin, tạo dòng là giữ". Cái giá hiện ra sau hai tuần rưỡi:

    S010  844 mẫu   Ảnh | Khoa | Minh | Nhung | Thư | Trân   <- SÁU người
    S011   55 mẫu   Khoa | Minh | Trân                       <- ba người

Một hàng máy sinh gộp sáu người thật thành một danh tính. Vì nó nằm trong
`signers`, mọi phép đếm và mọi phép chia tập theo người ký đều coi nó là MỘT
người — 899/1678 mẫu có người ký đang trỏ vào hai hàng như thế.

Chính sách được ghim ở đây
--------------------------
    danh tính chắc chắn  -> signer_id chuẩn
    chưa biết / mơ hồ    -> signer_id = NULL
    nhãn cũ              -> giữ nguyên samples.user_id làm chứng cứ

Không có nhánh thứ tư. Tệp này canh cả hai tầng — đường GHI lúc chạy và đường
SỬA CHỮA lúc migrate — vì chính sách chỉ đúng khi cả hai cùng tuân.
"""

from __future__ import annotations

import uuid

import psycopg2
import pytest

from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def cur():
    from app.storage.rls import apply_scope

    conn = psycopg2.connect(db.settings.database_url)
    conn.autocommit = False
    try:
        with system_scope("test: chinh sach nguoi ky"):
            with conn.cursor() as c:
                apply_scope(c)
                yield c
    finally:
        conn.rollback()
        conn.close()


def _tenant_va_lop(cur):
    tid = f"test-{uuid.uuid4().hex[:8]}"
    cur.execute("INSERT INTO tenants(tenant_id, display_name, slug) VALUES(%s,%s,%s)",
                (tid, "Thử người ký", tid))
    cls = f"cls_{uuid.uuid4().hex[:8]}"
    cur.execute(
        "INSERT INTO classes(class_uid, tenant_id, slug, label_original, language, "
        "region, is_active) VALUES(%s,%s,'n','N','vn','common',true)", (cls, tid))
    return tid, cls


# ------------------------------------------------- câu backfill đã biến mất

def test_khong_con_cau_tu_sinh_signer_trong_migration():
    """Phép khẳng định trung tâm: câu ấy không được quay lại.

    Kiểm theo NỘI DUNG chứ không theo tên biến, vì một lượt sửa sau này có thể
    dựng lại cùng hành vi dưới một cái tên khác — và đó mới là thứ nguy hiểm.
    """
    from app.storage.metadata_db import (
        DDL_STATEMENTS, INDEX_STATEMENTS, MIGRATION_STATEMENTS)
    from app.storage.authz_schema import AUTHZ_DDL_STATEMENTS

    tat_ca = [
        s for s in (*DDL_STATEMENTS, *MIGRATION_STATEMENTS,
                    *INDEX_STATEMENTS, *AUTHZ_DDL_STATEMENTS)
        if isinstance(s, str)
    ]
    pham = [
        " ".join(s.split())[:120] for s in tat_ca
        if "INSERT INTO signers" in s.replace("  ", " ")
    ]
    assert pham == [], (
        "một câu migration lại tạo hàng `signers`. Chưa biết người ký thì để "
        f"NULL — xem docstring tệp này. Câu vi phạm: {pham}")


def test_migration_khong_con_dong_signer_may_sinh_nao_moi(cur):
    """Đối chứng trên dữ liệu thật: không có hàng `signers` nào mang dấu vết
    của lượt tự sinh SAU ngày gỡ câu ấy."""
    cur.execute(
        "SELECT count(*) FROM signers WHERE note LIKE %s AND created_at > %s",
        ("tu sinh%", "2026-08-24"))
    assert cur.fetchone()[0] == 0


# ------------------------------------------------------ khoá ngoại phải chặn

def test_mau_tro_toi_signer_khong_ton_tai_thi_BI_TU_CHOI(cur):
    """Đúng tình huống mà câu backfill từng "chữa".

    Nay nó phải hỏng TO và hỏng ngay, chứ không được im lặng mọc ra một người.
    """
    tid, cls = _tenant_va_lop(cur)
    cur.execute("SELECT count(*) FROM signers")
    truoc = cur.fetchone()[0]

    # SAVEPOINT chứ không phải ROLLBACK trần, và đây là chỗ dễ đo nhầm nhất.
    # Phạm vi RLS được đặt bằng `set_config(..., true)` nên nó sống THEO GIAO
    # DỊCH; một `ROLLBACK` đầy đủ xoá luôn phạm vi, và câu `count` sau đó trả 0
    # vì bị chính sách lọc sạch — trông y hệt "bảng rỗng". Bản đầu của bài này
    # đỏ với `assert 0 == 6` đúng vì lý do đó.
    cur.execute("SAVEPOINT truoc_khi_thu")
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute(
            "INSERT INTO samples(sample_uid, tenant_id, class_uid, signer_id, "
            "seq_len, augment_id, file_path) "
            "VALUES(%s, %s, %s, 'S_KHONG_CO', 60, 0, 'x.npz')",
            (uuid.uuid4().hex[:10], tid, cls))
    cur.execute("ROLLBACK TO SAVEPOINT truoc_khi_thu")

    cur.execute("SELECT count(*) FROM signers")
    assert cur.fetchone()[0] == truoc, "không hàng `signers` nào được sinh thêm"


def test_mau_chua_biet_nguoi_ky_thi_ghi_duoc_voi_NULL(cur):
    """Nửa còn lại của chính sách, và không có nó thì bài trên vô nghĩa:
    "chưa biết" phải là một trạng thái GHI ĐƯỢC, nếu không đường ghi sẽ lại đi
    tìm cách bịa ra một giá trị cho xong."""
    tid, cls = _tenant_va_lop(cur)
    uid = uuid.uuid4().hex[:10]
    cur.execute(
        "INSERT INTO samples(sample_uid, tenant_id, class_uid, signer_id, "
        "seq_len, augment_id, file_path) VALUES(%s, %s, %s, NULL, 60, 0, 'x.npz')",
        (uid, tid, cls))
    cur.execute("SELECT signer_id FROM samples WHERE sample_uid = %s", (uid,))
    assert cur.fetchone()[0] is None


def test_chay_lai_migration_KHONG_bien_NULL_thanh_S0xx(cur):
    """Kịch bản bạn lo nhất: mẫu chưa rõ người ký, rồi ai đó chạy migrate.

    Trước 24/08/2026 lượt ấy sẽ nhìn thấy tham chiếu thiếu và "chữa" bằng cách
    đẻ ra một signer. Nay nó phải để nguyên NULL.
    """
    tid, cls = _tenant_va_lop(cur)
    uid = uuid.uuid4().hex[:10]
    cur.execute(
        "INSERT INTO samples(sample_uid, tenant_id, class_uid, signer_id, "
        "seq_len, augment_id, file_path) VALUES(%s, %s, %s, NULL, 60, 0, 'x.npz')",
        (uid, tid, cls))
    cur.execute("SELECT count(*) FROM signers")
    truoc = cur.fetchone()[0]

    # Phát lại đúng nhóm câu mà một lượt migrate chạy trên mặt phẳng người ký.
    # Không gọi `migrate_database()` vì nó cần kết nối riêng và sẽ commit —
    # tệp này cố ý ở trong một giao dịch tự hoàn tác.
    from app.storage.metadata_db import MIGRATION_STATEMENTS
    for s in MIGRATION_STATEMENTS:
        if isinstance(s, str) and "signers" in s and s.strip().upper().startswith("INSERT"):
            cur.execute(s)

    cur.execute("SELECT signer_id FROM samples WHERE sample_uid = %s", (uid,))
    assert cur.fetchone()[0] is None, "migrate không được điền người ký cho mẫu chưa rõ"
    cur.execute("SELECT count(*) FROM signers")
    assert cur.fetchone()[0] == truoc, "migrate không được sinh thêm hàng `signers`"


# --------------------------------------------- runtime khớp theo DANH TÍNH

def test_resolve_signer_khop_theo_UUID_chu_khong_theo_TEN():
    """Nguồn gốc của cả mớ hỗn loạn là khớp theo tên. `Trâm`/`Tram`,
    `Thu Ngân`/`Thungan`/`Ngan` là cùng người viết ba kiểu, còn `Minh` thì lại
    là NHIỀU người. Tên không phải danh tính.

    Bài này đọc mã chứ không chạy: nó canh việc phép khớp KHÔNG được lặng lẽ
    đổi sang so tên ở một lượt sửa sau.
    """
    import inspect

    from app import signers

    nguon = inspect.getsource(signers.resolve_signer_for_user)
    # Phép khớp ĐỌC trường nào của hàng đang duyệt — đó mới là câu hỏi. Hàm
    # vẫn được phép GHI `display_name` vào hàng mới; ghi tên khác hẳn khớp
    # bằng tên.
    assert 'r.get("external_user_id")' in nguon, "phải khớp bằng UUID tài khoản"
    assert 'r.get("display_name")' not in nguon, (
        "đọc display_name của hàng đang duyệt nghĩa là đang khớp bằng TÊN — "
        "`Trâm`/`Tram` là một người viết hai kiểu, còn `Minh` là nhiều người")
