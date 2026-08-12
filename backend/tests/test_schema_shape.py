"""Hình dạng lược đồ: không bảng mồ côi, không liên kết mồ côi, bảng mới có mặt.

Tách từ `test_schema_v3.py` (593 dòng, bốn mối quan tâm không liên quan gộp
chung). Bối cảnh đầy đủ của đợt vá lược đồ: `docs/needFix/SAAS_SCHEMA_DESIGN.md`
§9sexies.
"""

from __future__ import annotations


import pytest

from app.storage import metadata_db as db
from app.storage import rls


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()

# ------------------------------------------------------------- không mồ côi

#: Hai bảng được phép đứng một mình, và lý do phải viết ra chứ không ngầm hiểu.
#: Bất kỳ bảng nào khác không tham gia một khoá ngoại nào sẽ làm đỏ test bên
#: dưới — đó là điểm của nó.
STANDALONE_BY_DESIGN = {
    # Con trỏ phân trang của Google Sheets: một dòng cho mỗi tên bảng, không
    # thuộc tenant nào và không tham chiếu gì. Nối nó vào đâu cũng là gượng ép.
    "google_sheets_sync_status",
    # Khoá công khai của máy ghi SOT. `added_by` cố ý là TEXT chứ không phải
    # khoá ngoại tới `users`: máy đăng ký khoá thường không phải một tài khoản
    # trong cơ sở dữ liệu này, và một khoá phải sống lâu hơn người thêm nó.
    "sot_authorized_keys",
    # Sổ ghi việc một tenant đã bị XOÁ VĨNH VIỄN. Không thể có khoá ngoại tới
    # `tenants`: chính hàng nó tham chiếu là hàng vừa bị xoá, nên ràng buộc sẽ
    # khiến hành động mà nó tồn tại để ghi lại trở nên bất khả thi. `tenant_id`
    # ở đây là chữ, là dấu vết, không phải một liên kết. Xem
    # `app/tenant_lifecycle.py`.
    "tenant_purges",
    # Sổ đăng bạ văn bản pháp lý. Cùng nguyên tắc với `tenant_purges`, và ở đây
    # nó đã trả giá để học: bản đầu CÓ khoá ngoại `actor_user_id -> users
    # ON DELETE SET NULL`. `SET NULL` phát ra một UPDATE, trigger chỉ-thêm từ
    # chối UPDATE, nên `DELETE FROM users` thất bại cho bất kỳ ai từng xuất hiện
    # trong sổ — tức là sổ đăng bạ đã âm thầm làm hỏng quyền xoá tài khoản.
    #
    # Nguyên tắc: MỘT SỔ ĐĂNG BẠ KHÔNG ĐƯỢC CẢN CHÍNH HÀNH ĐỘNG NÓ GHI LẠI.
    # Danh tính người thao tác giữ ở `actor_label`, điền ngay lúc ghi.
    "legal_document_events",
    # Sổ đăng bạ phiên bản LƯỢC ĐỒ. Nó đứng ở một bậc khác với mọi bảng còn
    # lại: những bảng kia mô tả dữ liệu, bảng này mô tả *hình dạng* của chúng.
    # Không có gì để trỏ tới — `applied_by` là tên vai Postgres (`voya_app`,
    # `admin`), không phải một hàng trong `users`, và `applied_on` là định danh
    # MÁY.
    #
    # Nó cũng phải đọc được KHI mọi thứ khác còn chưa tồn tại: cổng phiên bản
    # ở `app/db.py` hỏi nó trên một cơ sở dữ liệu có thể chưa có bảng nào khác.
    # Một khoá ngoại ở đây sẽ biến "hỏi phiên bản" thành "phụ thuộc vào bảng
    # được trỏ tới", đúng vòng phụ thuộc mà cổng tồn tại để cắt.
    "schema_migrations",
}


def _tables() -> set[str]:
    return {
        r["table_name"]
        for r in db._fetch_all(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
    }


def _tables_in_any_foreign_key() -> set[str]:
    rows = db._fetch_all(
        "SELECT c.relname AS src, f.relname AS dst FROM pg_constraint k "
        "JOIN pg_class c ON c.oid = k.conrelid "
        "JOIN pg_class f ON f.oid = k.confrelid "
        "WHERE k.contype = 'f'"
    )
    out: set[str] = set()
    for r in rows:
        out.add(r["src"])
        out.add(r["dst"])
    return out


def test_no_table_is_an_orphan():
    """Mọi bảng phải tham gia ít nhất một khoá ngoại, hoặc nằm trong danh sách
    miễn trừ có ghi lý do.

    Đây là bài kiểm tra đúng cho yêu cầu "không có bảng nào mồ côi". Một bảng
    không nối với gì thì hoặc là mã chết, hoặc là một quan hệ mà ai đó quên
    khai báo — và cả hai đều là thứ phải phát hiện lúc này, không phải hai năm
    sau khi có người dựa vào nó.
    """
    orphans = sorted(_tables() - _tables_in_any_foreign_key() - STANDALONE_BY_DESIGN)
    assert not orphans, (
        f"những bảng này không tham gia khoá ngoại nào: {orphans}. Hoặc nối "
        f"chúng vào lược đồ, hoặc thêm vào STANDALONE_BY_DESIGN kèm lý do."
    )


def test_tenant_purge_order_covers_every_tenant_table():
    """Fixture dọn tenant tạm phải biết MỌI bảng có `tenant_id`.

    Đây là lỗi tôi vừa suýt để lại: thêm sáu bảng vào `TENANT_SCOPED_TABLES`
    khiến chúng có khoá ngoại `ON DELETE RESTRICT` tới `tenants`, nhưng
    `_TENANT_PURGE_ORDER` trong `conftest.py` không được cập nhật. Hậu quả
    không xuất hiện ngay — chỉ khi một test nào đó tạo phiên thu cho tenant tạm
    thì lệnh dọn mới bị từ chối, và tenant rác nằm lại trong danh sách của
    người vận hành. Test này biến "sẽ hỏng lúc nào đó" thành "đỏ ngay bây giờ".
    """
    from conftest import _TENANT_PURGE_ORDER

    thieu = sorted(set(db.TENANT_SCOPED_TABLES) - set(_TENANT_PURGE_ORDER) - {"users"})
    assert not thieu, (
        f"những bảng này có tenant_id nhưng purge_tenant không xoá: {thieu}. "
        f"Thêm vào _TENANT_PURGE_ORDER ĐÚNG VỊ TRÍ phụ thuộc — nối vào cuối "
        f"sẽ hỏng vì con phải đi trước cha."
    )


def test_the_dead_tables_are_gone():
    """`user_profiles`: 0 dòng, và `grep -rn user_profiles app/` không ra dòng
    Python nào. Chân dung người đóng góp đã nằm ở `signers`."""
    assert db.schema_debt()["dead_tables_still_present"] == []


def test_roles_was_kept_because_it_had_data():
    """Phản chứng cho test bên trên: `roles` cũng không mã nào đọc, nhưng nó có
    3 dòng thật và tài khoản đang trỏ tới. Bỏ một bảng có dữ liệu vì "không ai
    đọc" là mất dữ liệu. Thông tin được CHUYỂN sang `tenant_members.role`, và
    bảng nguồn ở lại làm đường đối chiếu."""
    assert "roles" in _tables()


# ------------------------------------------------- liên kết mồ côi đã được vá

def test_every_integrity_foreign_key_is_in_force():
    """`_run_ddl` hạ mọi thất bại xuống một dòng cảnh báo, nên "migration đã
    chạy" và "ràng buộc đang bảo vệ" là hai sự thật khác nhau."""
    assert db.missing_integrity_constraints() == []


def test_schema_debt_is_zero():
    debt = db.schema_debt()
    assert not any(debt.values()), f"schema còn nợ: {debt}"


def test_the_fk_specs_parse_and_name_real_tables():
    """`INTEGRITY_FK_SPECS` là nguồn cho ba nơi (migration, kiểm toán, test).
    Một phần tử sai định dạng sẽ làm cả ba im lặng bỏ qua."""
    tables = _tables()
    for spec in db.INTEGRITY_FK_SPECS:
        parts = spec.split("~")
        assert len(parts) == 3, f"spec sai định dạng: {spec!r}"
        table, name, definition = parts
        assert table in tables, f"{name} trỏ tới bảng không tồn tại: {table}"
        assert definition.startswith("FOREIGN KEY"), f"{name} không phải khoá ngoại"


def test_no_duplicate_constraint_names():
    names = [s.split("~")[1] for s in db.INTEGRITY_FK_SPECS]
    assert len(names) == len(set(names)), "hai spec dùng chung một tên ràng buộc"


# ------------------------------------------------------------- bảng mới có mặt

@pytest.mark.parametrize("table", [
    "capture_sessions", "vocabulary_groups", "signer_consents",
    "signer_aliases", "training_job_classes", "audit_log",
])
def test_new_table_exists(table):
    assert table in _tables()


def test_samples_gained_a_link_to_its_session_without_losing_the_old_columns():
    """Cột cũ phải còn nguyên.

    `session_uid` NULL ở 2.869/3.860 dòng và 28 nhóm (class, session_id) mang
    nhiều `session_uid` khác nhau, nên tái dùng cột đó làm khoá ngoại sẽ phải
    ghi đè nó. Phiên thu được cấp cột RIÊNG; hai cột cũ không bị đụng tới.
    """
    cols = {
        r["column_name"]
        for r in db._fetch_all(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'samples'"
        )
    }
    assert "capture_session_id" in cols
    assert "session_uid" in cols, "cột cũ bị xoá — đó là mất dữ liệu"
    assert "session_id" in cols, "cột cũ bị xoá — đó là mất dữ liệu"


# ------------------------------------------------------------- RLS bảng mới

def test_every_tenant_scoped_new_table_is_under_rls():
    for table in ("capture_sessions", "vocabulary_groups", "signer_consents",
                  "signer_aliases", "training_job_classes", "audit_log"):
        assert table in rls.RLS_TABLES, f"{table} có tenant_id nhưng không chịu RLS"


def test_rls_is_enabled_and_forced_on_every_listed_table():
    """ENABLE thôi chưa đủ: chủ sở hữu bảng bỏ qua chính sách trừ khi FORCE."""
    rows = db._fetch_all(
        "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE relname = ANY(%s)", (list(rls.RLS_TABLES),)
    )
    by_name = {r["relname"]: r for r in rows}
    for table in rls.RLS_TABLES:
        row = by_name.get(table)
        assert row is not None, f"{table} không tồn tại"
        assert row["relrowsecurity"], f"{table}: RLS chưa bật"
        assert row["relforcerowsecurity"], f"{table}: RLS chưa FORCE"


