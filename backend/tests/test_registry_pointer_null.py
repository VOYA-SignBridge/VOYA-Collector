"""Con trỏ "registry hiện hành": chưa công bố gì thì NULL, không phải 0 hay 1.

Vết đã đo ngày 24/08/2026
-------------------------
Khoá ngoại ghép `(tenant_id, version) -> registry_versions` thêm ngày 23/08 là
đúng về nguyên tắc, nhưng nó được gắn lên một cột đang mang HAI giá trị mốc
bịa, và cả hai chỉ xuất hiện ở đường GHI chứ không có trong dữ liệu:

    clone_catalog_to_tenant  ghi 0   phiên bản 0 KHÔNG BAO GIỜ tồn tại
    DEFAULT của cột           là 1   phiên bản 1 chưa chắc tồn tại

Hậu quả: `tenant_admin.create_tenant` gọi `clone_catalog_to_tenant` không bọc
lỗi, nên **tạo tenant mới hỏng**. Đo bằng chính câu lệnh ấy:

    INSERT INTO vocabulary_registry_meta(tenant_id, version) VALUES('probe',0)
    ERROR: violates foreign key constraint fk_vocabulary_registry_meta_version

v7 KHÔNG gỡ khoá ngoại. Cột vốn đã có sẵn cách nói "chưa có gì" mà không phải
bịa số: NULL. MATCH SIMPLE cho NULL đi qua, nên phép kiểm còn nguyên mà trạng
thái rỗng vẫn biểu diễn được.

Tệp này canh hai phía, và thiếu phía nào thì bản vá cũng qua được:

    phía CHO PHÉP   trạng thái rỗng và mọi bước publish hợp lệ phải chạy
    phía CHẶN       con trỏ trỏ vào phiên bản không tồn tại vẫn phải bị từ chối

Không có phía thứ hai, "gỡ khoá ngoại cho xong" cũng xanh hết.
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
    """Cursor phạm vi hệ thống, luôn hoàn tác."""
    from app.storage.rls import apply_scope

    conn = psycopg2.connect(db.settings.database_url)
    conn.autocommit = False
    try:
        with system_scope("test: con tro registry"):
            with conn.cursor() as c:
                apply_scope(c)
                yield c
    finally:
        conn.rollback()
        conn.close()


def _tenant(cur):
    tid = f"test-{uuid.uuid4().hex[:8]}"
    cur.execute("INSERT INTO tenants(tenant_id, display_name, slug) VALUES(%s,%s,%s)",
                (tid, "Thử con trỏ", tid))
    return tid


# ------------------------------------------------------------ phía CHO PHÉP

def test_tenant_moi_chua_cong_bo_gi_thi_con_tro_la_NULL(cur):
    """Đúng câu lệnh mà `clone_catalog_to_tenant` chạy. Trước v7 nó bị chặn."""
    tid = _tenant(cur)
    cur.execute(
        "INSERT INTO vocabulary_registry_meta(tenant_id, version) VALUES(%s, NULL) "
        "ON CONFLICT (tenant_id) DO NOTHING", (tid,))
    cur.execute("SELECT version FROM vocabulary_registry_meta WHERE tenant_id = %s",
                (tid,))
    assert cur.fetchone()[0] is None


def test_cot_khong_con_DEFAULT_de_roi_vao(cur):
    """DEFAULT 1 là giá trị mốc bịa thứ hai, và nó nguy hiểm hơn số 0 vì nó
    xuất hiện khi người viết KHÔNG nêu cột nào cả."""
    cur.execute(
        "SELECT column_default, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'vocabulary_registry_meta' AND column_name = 'version'")
    mac_dinh, nullable = cur.fetchone()
    assert mac_dinh is None, "còn DEFAULT thì một INSERT im lặng lại dựng con trỏ treo"
    assert nullable == "YES"


def test_khong_con_hang_nao_mang_moc_0(cur):
    """Hậu điều kiện của bước dữ liệu v7, kiểm như một bất biến sống."""
    cur.execute("SELECT count(*) FROM vocabulary_registry_meta WHERE version = 0")
    assert cur.fetchone()[0] == 0


def test_cong_bo_lan_dau_tu_NULL_roi_lan_hai(cur):
    """Thứ tự publish là phần dễ hỏng nhất của v7.

    Bản `_bump()` cũ dời con trỏ TRƯỚC rồi mới tạo `registry_versions`, nên
    chính khoá ngoại này chặn nó. Bài test đi hai lượt: lượt đầu từ trạng thái
    rỗng (NULL -> 1), lượt sau từ trạng thái đã có (1 -> 2). Chỉ kiểm lượt đầu
    thì một bản vá chỉ chữa nhánh "chưa có dòng" vẫn qua.
    """
    tid = _tenant(cur)
    cur.execute("INSERT INTO vocabulary_registry_meta(tenant_id, version) "
                "VALUES(%s, NULL)", (tid,))

    for mong_doi in (1, 2):
        cur.execute("SELECT COALESCE(version, 0) FROM vocabulary_registry_meta "
                    "WHERE tenant_id = %s", (tid,))
        ke_tiep = int(cur.fetchone()[0]) + 1
        # TẠO phiên bản thật TRƯỚC — đúng thứ tự mà `_bump()` nay dùng.
        cur.execute(
            "INSERT INTO registry_versions(tenant_id, version, content_hash, snapshot) "
            "VALUES(%s, %s, %s, '{}'::jsonb)", (tid, ke_tiep, f"hash{ke_tiep}"))
        cur.execute(
            "INSERT INTO vocabulary_registry_meta(tenant_id, version) VALUES(%s,%s) "
            "ON CONFLICT (tenant_id) DO UPDATE SET version = EXCLUDED.version",
            (tid, ke_tiep))

        cur.execute("SELECT version FROM vocabulary_registry_meta WHERE tenant_id = %s",
                    (tid,))
        assert cur.fetchone()[0] == mong_doi


def test_thu_tu_nguoc_lai_thi_bi_chan(cur):
    """Đối chứng cho bài trên: nếu ai đó khôi phục thứ tự cũ — dời con trỏ
    trước — khoá ngoại phải từ chối. Không có bài này thì bài trên chỉ chứng
    minh "thứ tự mới chạy được", không chứng minh "thứ tự cũ đã hỏng"."""
    tid = _tenant(cur)
    cur.execute("INSERT INTO vocabulary_registry_meta(tenant_id, version) "
                "VALUES(%s, NULL)", (tid,))
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute("UPDATE vocabulary_registry_meta SET version = 1 "
                    "WHERE tenant_id = %s", (tid,))


# ---------------------------------------------------------------- phía CHẶN

def test_con_tro_vao_phien_ban_khong_ton_tai_van_bi_tu_choi(cur):
    tid = _tenant(cur)
    cur.execute("INSERT INTO vocabulary_registry_meta(tenant_id, version) "
                "VALUES(%s, NULL)", (tid,))
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute("UPDATE vocabulary_registry_meta SET version = 999999 "
                    "WHERE tenant_id = %s", (tid,))


def test_khong_xoa_duoc_phien_ban_dang_bi_tro_toi(cur):
    """Con trỏ phải luôn trỏ vào thứ có thật — kể cả theo hướng ngược lại."""
    tid = _tenant(cur)
    cur.execute(
        "INSERT INTO registry_versions(tenant_id, version, content_hash, snapshot) "
        "VALUES(%s, 1, 'h', '{}'::jsonb)", (tid,))
    cur.execute("INSERT INTO vocabulary_registry_meta(tenant_id, version) "
                "VALUES(%s, 1)", (tid,))
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute("DELETE FROM registry_versions WHERE tenant_id = %s AND version = 1",
                    (tid,))


def test_con_tro_khong_vat_qua_tenant(cur):
    """Khoá ngoại là GHÉP, nên phiên bản của tổ chức khác không dùng lại được."""
    a, b = _tenant(cur), _tenant(cur)
    cur.execute(
        "INSERT INTO registry_versions(tenant_id, version, content_hash, snapshot) "
        "VALUES(%s, 7, 'h', '{}'::jsonb)", (b,))
    cur.execute("INSERT INTO vocabulary_registry_meta(tenant_id, version) "
                "VALUES(%s, NULL)", (a,))
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute("UPDATE vocabulary_registry_meta SET version = 7 "
                    "WHERE tenant_id = %s", (a,))


def test_toan_bo_con_tro_hien_co_deu_tro_vao_thu_co_that(cur):
    """Bất biến mà khoá ngoại sinh ra để giữ, phát biểu ĐỘC LẬP với nó.

    Nếu một lượt sửa sau này gỡ khoá ngoại, câu này vẫn phải đúng — và nó sẽ
    là thứ báo động, chứ không phải sự im lặng.
    """
    cur.execute(
        "SELECT count(*) FROM vocabulary_registry_meta m "
        "WHERE m.version IS NOT NULL AND NOT EXISTS ("
        "   SELECT 1 FROM registry_versions r "
        "    WHERE r.tenant_id = m.tenant_id AND r.version = m.version)")
    assert cur.fetchone()[0] == 0
