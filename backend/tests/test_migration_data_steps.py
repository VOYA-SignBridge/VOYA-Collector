"""Bước ĐỊNH HÌNH DỮ LIỆU của migration: phạm vi hẹp, và HẬU ĐIỀU KIỆN.

Vì sao tệp này tồn tại
======================
Tới 15/08/2026 migration chỉ chạy đúng vì sản xuất dùng vai `admin`
(SUPERUSER, BYPASSRLS). Dưới vai tối thiểu mà chính hệ thống này khuyến nghị —
`voya_test_owner`, NOSUPERUSER, NOBYPASSRLS — bốn câu định hình dữ liệu hỏng,
và hỏng theo ba kiểu khác nhau, không kiểu nào làm migration đỏ:

    UPDATE classes SET region=...        -> UPDATE 0, KHÔNG ném lỗi
    INSERT INTO tenants(default)         -> ném lỗi, `_run_ddl` NUỐT
    INSERT INTO vocabulary_registry_meta -> ném lỗi, `_run_ddl` NUỐT
    UPDATE tenants SET tenant_type=...   -> UPDATE 0, KHÔNG ném lỗi

Câu cuối là câu đáng sợ nhất và là lý do hợp đồng migration cần vế thứ ba.
`required_objects` và `retired_objects` hỏi "đối tượng có mặt/vắng mặt chưa";
cả hai đều trả lời ĐÚNG trong khi trạng thái dữ liệu vẫn sai. Và bắt ngoại lệ
cũng không cứu được: `UPDATE 0` không phải ngoại lệ. Chỉ `required_postconditions`
— hỏi trạng thái CUỐI — phân biệt được "vốn đã đúng" với "vừa bị RLS nuốt".

Hai lỗi độc lập nằm chồng nhau
==============================
Câu gieo tenant `community` còn mang `plan_code = 'internal'`, mã gói mà Billing
v6 đã đổi tên và XOÁ khỏi `plans`. Máy đang chạy sống sót vì dòng đó ra đời
trước v6 rồi được đổi tên cùng mọi tenant khác. Trên bản cài mới nó vi phạm
`fk_tenants_plan` — hoàn toàn không liên quan tới RLS. Bọc phạm vi hệ thống chỉ
biến một lỗi im lặng thành một lỗi ồn ào, nên `TestMaGoiCuaTenantCongDong` khoá
riêng lỗi ấy.

Điều tệp này CỐ Ý không khẳng định
==================================
`app.system_scope` vẫn tự đặt được bởi vai ứng dụng — giới hạn TCB **Mức II**,
ghi ở docs/TENANT_ISOLATION_AND_AUTHZ.md §4.1. Không phép kiểm nào ở đây chứng
minh phạm vi hệ thống chống được một `voya_app` đã bị chiếm. Thứ được chứng
minh là hẹp hơn nhiều và vẫn đáng giá: bộ thực thi migration mở phạm vi ĐÚNG
những bước đã đăng ký, NÓI RA mình mở để làm gì, và TỪ CHỐI đi tiếp khi trạng
thái đích không đạt.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------


@contextmanager
def _pham_vi_dung_trang_thai(cur):
    """Phạm vi hệ thống cho phần DỰNG TRẠNG THÁI của bài kiểm.

    Bản thân bài kiểm cũng bị RLS chặn y như migration — `tenants` đang FORCE
    RLS và `voya_test_owner` là chủ sở hữu bảng. Không có khối này thì câu dựng
    trạng thái `UPDATE 0` và bài kiểm chạy trên một tiền đề không có thật.

    Theo PHIÊN chứ không theo giao dịch, vì `_migration_cursor` là autocommit;
    `finally` gỡ lại để không rò sang bài kiểm sau trên cùng kết nối.
    """
    cur.execute("SELECT set_config('app.system_scope', 'on', false)")
    try:
        yield cur
    finally:
        cur.execute("SELECT set_config('app.system_scope', '', false)")


def _dat(cur, postcondition: str) -> bool:
    """Đánh giá hậu điều kiện TRONG phạm vi — xem `_run_data_step`."""
    with _pham_vi_dung_trang_thai(cur):
        cur.execute(postcondition)
        return bool(cur.fetchone()[0])


def _chay_buoc(cur, cau_dan_dau: str) -> None:
    """Chạy đúng một bước qua BỘ THỰC THI THẬT, không dựng lại khuôn của nó."""
    from app.storage.metadata_db import _run_ddl

    _run_ddl(cur, [cau_dan_dau], "test")


@pytest.fixture
def cur():
    from app.storage.metadata_db import _migration_cursor

    with _migration_cursor() as c:
        yield c


@pytest.fixture
def khong_dang_ky(monkeypatch):
    """Gỡ một bước khỏi sổ đăng ký — tức gỡ phạm vi hệ thống của nó.

    Câu vẫn nằm nguyên trong danh sách DDL và vẫn được chạy; nó chỉ mất đường
    đặc biệt và rơi về nhánh "nuốt lỗi rồi đi tiếp" như trước 15/08/2026. Đó
    đúng là hình dạng của lỗi cũ.
    """
    def _go(cau_dan_dau: str):
        from app.storage import metadata_db as mdb

        goc = mdb._data_steps()
        con_lai = {k: v for k, v in goc.items() if k != cau_dan_dau}
        theo_sau = frozenset(
            s for _, cac, _ in con_lai.values() for s in cac[1:])
        monkeypatch.setattr(mdb, "_data_steps", lambda: con_lai)
        monkeypatch.setattr(mdb, "_data_step_followers", lambda: theo_sau)

    return _go


# ---------------------------------------------------------------------------
# 1. vocabulary_registry_meta cho tenant nền tảng
# ---------------------------------------------------------------------------


@pytest.fixture
def vocab_meta_vang(cur):
    """Xoá dòng meta của tenant nền tảng, và trả lại sau bài kiểm.

    Xoá được sạch: bảng không có khoá ngoại nào trỏ vào. `version` được ghi lại
    rồi phục hồi nguyên vẹn — nó là con trỏ tới bản chụp registry đang dùng, và
    một bài kiểm không có quyền tua ngược nó.
    """
    from app.tenancy import DEFAULT_TENANT_ID

    with _pham_vi_dung_trang_thai(cur):
        cur.execute("SELECT version FROM vocabulary_registry_meta "
                    "WHERE tenant_id = %s", (DEFAULT_TENANT_ID,))
        row = cur.fetchone()
        cu = row[0] if row else None
        cur.execute("DELETE FROM vocabulary_registry_meta WHERE tenant_id = %s",
                    (DEFAULT_TENANT_ID,))
    try:
        yield
    finally:
        with _pham_vi_dung_trang_thai(cur):
            cur.execute("DELETE FROM vocabulary_registry_meta WHERE tenant_id = %s",
                        (DEFAULT_TENANT_ID,))
            if cu is not None:
                cur.execute(
                    "INSERT INTO vocabulary_registry_meta(tenant_id, version) "
                    "VALUES(%s, %s)", (DEFAULT_TENANT_ID, cu))


class TestGieoVocabularyRegistryMeta:
    def test_dong_vang_thi_buoc_tao_dung_mot_dong(self, cur, vocab_meta_vang):
        from app.storage.metadata_db import (
            _SQL_SEED_VOCAB_REGISTRY_META, _data_steps)

        _, _, hau_dieu_kien = _data_steps()[_SQL_SEED_VOCAB_REGISTRY_META]
        assert not _dat(cur, hau_dieu_kien), "tien de sai: dong van con do"

        _chay_buoc(cur, _SQL_SEED_VOCAB_REGISTRY_META)

        assert _dat(cur, hau_dieu_kien)

    def test_chay_lai_van_dung_mot_dong(self, cur, vocab_meta_vang):
        """Bước phải nhận ra trạng thái đã đúng, không nhân thêm dòng.

        `count(*) = 1` chứ không `>= 1`: một hậu điều kiện "có ít nhất một" sẽ
        chấm đạt cho đúng cái nó phải bắt.
        """
        from app.storage.metadata_db import (
            _SQL_SEED_VOCAB_REGISTRY_META, _data_steps)

        _, _, hau_dieu_kien = _data_steps()[_SQL_SEED_VOCAB_REGISTRY_META]
        _chay_buoc(cur, _SQL_SEED_VOCAB_REGISTRY_META)
        _chay_buoc(cur, _SQL_SEED_VOCAB_REGISTRY_META)

        assert _dat(cur, hau_dieu_kien)

    def test_M_D1_go_pham_vi_thi_dong_khong_bao_gio_ra_doi(
            self, cur, vocab_meta_vang, khong_dang_ky):
        """ĐỘT BIẾN M-D1 — gỡ phạm vi khỏi bước gieo registry meta.

        Không có phạm vi, `INSERT` bị WITH CHECK của RLS từ chối, `_run_ddl`
        nuốt ngoại lệ, và migration đi tiếp như không có gì. Đây chính là hành
        vi đã đo được ngày 15/08/2026.
        """
        from app.storage.metadata_db import (
            _SQL_SEED_VOCAB_REGISTRY_META, _data_steps)

        _, _, hau_dieu_kien = _data_steps()[_SQL_SEED_VOCAB_REGISTRY_META]
        khong_dang_ky(_SQL_SEED_VOCAB_REGISTRY_META)

        _chay_buoc(cur, _SQL_SEED_VOCAB_REGISTRY_META)   # không ném lỗi

        assert not _dat(cur, hau_dieu_kien), (
            "khong co pham vi ma dong VAN duoc tao — hoac RLS da bi noi long, "
            "hoac buoc nay khong con can pham vi va dang ky la thua")


# ---------------------------------------------------------------------------
# 2. Tenant cộng đồng — hai nhánh, một ý định
# ---------------------------------------------------------------------------


@pytest.fixture
def cong_dong_sai_loai(cur):
    """Dòng `community` TỒN TẠI nhưng sai loại — trạng thái cần SỬA.

    Đây là nhánh mà bài kiểm "dòng còn thiếu" không chạm tới, và là nhánh duy
    nhất chứng minh được lỗi `UPDATE 0`: câu INSERT có `WHERE NOT EXISTS` nên
    nó KHÔNG làm gì ở đây; chỉ câu sửa chữa mới đưa được trạng thái về đích.
    """
    from app.storage.authz_schema import COMMUNITY_TENANT_ID

    with _pham_vi_dung_trang_thai(cur):
        cur.execute("SELECT tenant_type, is_system_reserved FROM tenants "
                    "WHERE tenant_id = %s", (COMMUNITY_TENANT_ID,))
        row = cur.fetchone()
        assert row is not None, "tien de sai: chua co dong community de lam hong"
        loai_cu, reserved_cu = row
        # `uq_tenants_single_community` là chỉ mục một phần trên chính cột này,
        # nên hạ loại xuống ORGANIZATION không đụng ràng buộc nào.
        cur.execute(
            "UPDATE tenants SET tenant_type = 'ORGANIZATION', "
            "is_system_reserved = FALSE WHERE tenant_id = %s",
            (COMMUNITY_TENANT_ID,))
    try:
        yield COMMUNITY_TENANT_ID
    finally:
        with _pham_vi_dung_trang_thai(cur):
            cur.execute(
                "UPDATE tenants SET tenant_type = %s, is_system_reserved = %s "
                "WHERE tenant_id = %s",
                (loai_cu, reserved_cu, COMMUNITY_TENANT_ID))


class TestTenantCongDong:
    def test_dong_sai_loai_duoc_sua_ve_canonical(self, cur, cong_dong_sai_loai):
        from app.storage.authz_schema import (
            _SQL_SEED_COMMUNITY_TENANT, _SQL_POSTCOND_COMMUNITY_TENANT)

        assert not _dat(cur, _SQL_POSTCOND_COMMUNITY_TENANT), \
            "tien de sai: dong chua bi lam hong"

        _chay_buoc(cur, _SQL_SEED_COMMUNITY_TENANT)

        assert _dat(cur, _SQL_POSTCOND_COMMUNITY_TENANT)

    def test_chay_lai_tren_dong_da_dung_khong_doi_gi(self, cur):
        from app.storage.authz_schema import (
            COMMUNITY_TENANT_ID, _SQL_SEED_COMMUNITY_TENANT,
            _SQL_POSTCOND_COMMUNITY_TENANT)

        with _pham_vi_dung_trang_thai(cur):
            cur.execute("SELECT display_name, slug, plan_code FROM tenants "
                        "WHERE tenant_id = %s", (COMMUNITY_TENANT_ID,))
            truoc = cur.fetchone()

        _chay_buoc(cur, _SQL_SEED_COMMUNITY_TENANT)

        with _pham_vi_dung_trang_thai(cur):
            cur.execute("SELECT display_name, slug, plan_code FROM tenants "
                        "WHERE tenant_id = %s", (COMMUNITY_TENANT_ID,))
            sau = cur.fetchone()
        assert sau == truoc, "buoc chay lai da ghi de len trang thai dang co"
        assert _dat(cur, _SQL_POSTCOND_COMMUNITY_TENANT)

    def test_M_D2_go_pham_vi_thi_buoc_khong_sua_duoc_gi(
            self, cur, cong_dong_sai_loai, khong_dang_ky):
        """ĐỘT BIẾN M-D2 — gỡ phạm vi khỏi bước cộng đồng.

        Không phạm vi: cả INSERT lẫn UPDATE đều không thấy dòng nào, `UPDATE 0`
        không ném lỗi, và không có gì để `_run_ddl` ghi log.
        """
        from app.storage.authz_schema import (
            _SQL_SEED_COMMUNITY_TENANT, _SQL_POSTCOND_COMMUNITY_TENANT)

        khong_dang_ky(_SQL_SEED_COMMUNITY_TENANT)

        _chay_buoc(cur, _SQL_SEED_COMMUNITY_TENANT)

        assert not _dat(cur, _SQL_POSTCOND_COMMUNITY_TENANT), (
            "khong co pham vi ma dong VAN duoc sua — dang ky buoc nay la thua")

    def test_M_D3_bo_cau_sua_chua_thi_buoc_PHAI_dung(
            self, cur, cong_dong_sai_loai, monkeypatch):
        """ĐỘT BIẾN M-D3 — giữ phạm vi, bỏ câu SỬA CHỮA.

        Đây là ca mà bài kiểm "dòng còn thiếu" không bao giờ bắt được: chỉ còn
        câu INSERT thì trên một cơ sở dữ liệu trống nó vẫn tạo đúng dòng và mọi
        thứ vẫn xanh. Chỉ trạng thái "đã có mà sai" mới lộ ra rằng nhánh sửa
        chữa đã biến mất.

        Và nó phải NÉM chứ không phải im lặng: hậu điều kiện không đạt là dừng
        migration.
        """
        from app.storage import metadata_db as mdb
        from app.storage.authz_schema import (
            _SQL_SEED_COMMUNITY_TENANT, _SQL_POSTCOND_COMMUNITY_TENANT)

        goc = mdb._data_steps()
        ly_do, _, hau = goc[_SQL_SEED_COMMUNITY_TENANT]
        cut = dict(goc)
        cut[_SQL_SEED_COMMUNITY_TENANT] = (ly_do, (_SQL_SEED_COMMUNITY_TENANT,), hau)
        monkeypatch.setattr(mdb, "_data_steps", lambda: cut)
        monkeypatch.setattr(mdb, "_data_step_followers", lambda: frozenset())

        with pytest.raises(mdb.MigrationStepFailed) as loi:
            _chay_buoc(cur, _SQL_SEED_COMMUNITY_TENANT)

        assert "seed-community-tenant" in str(loi.value)
        assert not _dat(cur, _SQL_POSTCOND_COMMUNITY_TENANT)


class TestMaGoiCuaTenantCongDong:
    """Lỗi Billing v6, tách riêng vì nó KHÔNG phải lỗi RLS."""

    def test_ma_goi_trong_cau_gieo_phai_la_ma_ma_chinh_migration_tao_ra(self):
        """So hai HẰNG SỐ với nhau, không so với cơ sở dữ liệu đang chạy.

        Đây là điểm mấu chốt: trên máy này dòng `community` mang `enterprise`
        hợp lệ, nên mọi phép kiểm hỏi cơ sở dữ liệu đều xanh. Cái sai nằm ở câu
        gieo, và chỉ lộ ra trên một bản cài mới. Nên phép kiểm phải đọc câu gieo.
        """
        from app.storage.authz_schema import _SQL_SEED_COMMUNITY_TENANT
        from app.storage.metadata_db import MIGRATION_STATEMENTS

        seed_plans = next(
            (s for s in MIGRATION_STATEMENTS
             if isinstance(s, str) and "INSERT INTO plans (" in s), None)
        assert seed_plans, "khong tim thay cau gieo bang plans"
        co_san = set(re.findall(r"^\s*\('([a-z_]+)',", seed_plans, re.MULTILINE))
        assert co_san, "khong doc duoc ma goi nao tu cau gieo plans"

        dung = re.search(r"'COMMUNITY',\s*TRUE,\s*'([a-z_]+)'",
                         _SQL_SEED_COMMUNITY_TENANT)
        assert dung, "khong doc duoc plan_code cua cau gieo community"

        assert dung.group(1) in co_san, (
            f"cau gieo community dung plan_code={dung.group(1)!r} nhung cau gieo "
            f"plans chi tao {sorted(co_san)}. Tren mot ban cai moi, "
            f"fk_tenants_plan se tu choi — day chinh la loi Billing v6 "
            f"({dung.group(1)} da bi doi ten va xoa) quay lai.")


# ---------------------------------------------------------------------------
# 3. Backfill classes.region
# ---------------------------------------------------------------------------


@pytest.fixture
def mot_lop_thieu_vung(cur):
    """Một dòng `classes` có `region IS NULL` — trạng thái backfill sinh ra để xoá.

    Phải hạ `NOT NULL` trước, vì chính bước này là thứ đã dựng nó lên. Khôi
    phục ở `finally`; và nếu một lượt chạy hỏng giữa chừng thì
    `MIGRATION_MUST_SUCCEED` dựng lại ràng buộc ở lượt `ensure_tables()` kế
    tiếp — bộ test tự lành, không cần sửa tay.
    """
    with _pham_vi_dung_trang_thai(cur):
        cur.execute("SELECT class_uid, region FROM classes "
                    "WHERE region IS NOT NULL LIMIT 1")
        row = cur.fetchone()
        assert row is not None, "tien de sai: khong co lop nao de lam hong"
        uid, vung_cu = row
        cur.execute("ALTER TABLE classes ALTER COLUMN region DROP NOT NULL")
        cur.execute("UPDATE classes SET region = NULL WHERE class_uid = %s", (uid,))
    try:
        yield uid
    finally:
        with _pham_vi_dung_trang_thai(cur):
            cur.execute("UPDATE classes SET region = %s WHERE class_uid = %s",
                        (vung_cu, uid))
            cur.execute("ALTER TABLE classes ALTER COLUMN region SET NOT NULL")


class TestBackfillVung:
    def test_dong_thieu_vung_duoc_dien(self, cur, mot_lop_thieu_vung):
        from app.storage.metadata_db import _SQL_BACKFILL_CLASS_REGION, _data_steps

        _, _, hau = _data_steps()[_SQL_BACKFILL_CLASS_REGION]
        assert not _dat(cur, hau), "tien de sai: khong con dong NULL nao"

        _chay_buoc(cur, _SQL_BACKFILL_CLASS_REGION)

        assert _dat(cur, hau)

    def test_M_D4_go_pham_vi_thi_backfill_khong_dien_duoc_gi(
            self, cur, mot_lop_thieu_vung, khong_dang_ky):
        """ĐỘT BIẾN M-D4 — gỡ phạm vi khỏi bước backfill vùng.

        Đây là bước đầu tiên phát hiện ra cả lớp lỗi này, và là ví dụ thuần
        khiết nhất: `UPDATE 0` không ném lỗi, nên không có gì để bắt. Nếu ca
        này xanh khi đã gỡ phạm vi thì hoặc RLS trên `classes` đã bị nới, hoặc
        bài kiểm đang chạy dưới một vai có BYPASSRLS.
        """
        from app.storage.metadata_db import _SQL_BACKFILL_CLASS_REGION, _data_steps

        _, _, hau = _data_steps()[_SQL_BACKFILL_CLASS_REGION]
        khong_dang_ky(_SQL_BACKFILL_CLASS_REGION)

        _chay_buoc(cur, _SQL_BACKFILL_CLASS_REGION)   # không ném lỗi

        assert not _dat(cur, hau), (
            "khong co pham vi ma backfill VAN chay duoc — kiem lai vai dang "
            "dung co NOBYPASSRLS khong")

    def test_SET_NOT_NULL_la_cau_BAT_BUOC_nen_hong_la_DUNG(
            self, cur, mot_lop_thieu_vung):
        """Nửa sau của cặp: nếu backfill hụt, ràng buộc phải TỪ CHỐI, không nuốt.

        Không có `MIGRATION_MUST_SUCCEED` thì `_run_ddl` ghi một dòng cảnh báo
        rồi đi tiếp, cột vẫn nhận NULL, và vòng lặp tự nuôi quay lại ở lượt
        migration sau.
        """
        from app.storage.metadata_db import _SQL_CLASS_REGION_NOT_NULL

        with pytest.raises(Exception) as loi:
            _chay_buoc(cur, _SQL_CLASS_REGION_NOT_NULL)

        assert "null" in str(loi.value).lower()


# ---------------------------------------------------------------------------
# 4. Bản cài MỚI — thứ tự phụ thuộc không được bài kiểm dựng hộ
# ---------------------------------------------------------------------------


def _dsn_doi_ten_db(dsn: str, ten: str) -> str:
    return re.sub(r"/[^/?]+(\?|$)", f"/{ten}\\1", dsn)


@pytest.fixture
def csdl_trong(cur):
    """Một cơ sở dữ liệu TRỐNG, bỏ đi sau bài kiểm.

    Tiền tố `signdb_pytest_` là tiền tố duy nhất `conftest` cho phép, nên một
    lượt chạy lạc đích vẫn bị chặn ở cổng đó.
    """
    ten = f"signdb_pytest_{uuid.uuid4().hex[:10]}"
    cur.execute(f'CREATE DATABASE "{ten}"')
    try:
        yield ten
    finally:
        _bo_csdl_tam(cur, ten)


def _bo_csdl_tam(cur, ten: str, so_lan: int = 10) -> None:
    """Xoá cơ sở dữ liệu nháp, chịu được đường đua dọn kết nối của PostgreSQL.

    Vì sao bản đơn giản KHÔNG chạy ổn định
    --------------------------------------
    Bài kiểm ở lớp này gọi `app.cli.migrate` bằng TIẾN TRÌNH RIÊNG, và tiến
    trình ấy nối vào cơ sở dữ liệu nháp bằng CẢ HAI vai: `voya_test_owner` cho
    DSN migration và `voya_test_app` cho DSN ứng dụng. Khi tiến trình con thoát,
    PostgreSQL không dọn backend của nó tức khắc — trong một khoảng ngắn,
    `pg_stat_activity` vẫn còn dòng của vai ỨNG DỤNG.

    Dọn dẹp ở đây chạy dưới `voya_test_owner`, một vai NOSUPERUSER. Bắn
    `pg_terminate_backend` vào một backend thuộc vai khác thì PostgreSQL ném
    `InsufficientPrivilege` — và vì câu ấy giết cả lô trong MỘT lượt gọi, một
    dòng lạ làm hỏng toàn bộ lượt dọn, kể cả những backend mà vai này thừa
    quyền giết.

    Kết quả là một bài kiểm đỏ theo xác suất, đỏ vì đường đua dọn dẹp chứ không
    vì điều nó khẳng định. Đó là kiểu hỏng đắt nhất trong kho này: nó dạy người
    đọc rằng đỏ ở nhóm cách ly là chuyện thường, và lần đỏ THẬT sẽ bị bỏ qua.

    Ba tính chất
    ------------
    * **Giết TỪNG backend một**, nuốt lỗi từng cái. Vai này giết được cái nào
      thì giết cái đó; cái thuộc vai khác để PostgreSQL tự dọn.
    * **Thử lại `DROP`**, vì đường đua chỉ kéo dài vài chục mili giây.
    * **Hỏng thì NÓI RA ai đang giữ.** Nếu hết lượt vẫn không xoá được thì đây
      là rò kết nối thật, không phải đường đua — và thông báo phải đủ để chẩn
      đoán trong một lần đọc, chứ không phải một `InsufficientPrivilege` trần.
    """
    import time

    for lan in range(so_lan):
        cur.execute(
            "SELECT pid FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()", (ten,))
        for (pid,) in cur.fetchall():
            try:
                cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
            except Exception:                                    # noqa: BLE001
                # Backend của vai khác. Không giết được, và không cần giết —
                # nó sắp tự biến mất.
                pass
        try:
            cur.execute(f'DROP DATABASE IF EXISTS "{ten}"')
            return
        except Exception:                                        # noqa: BLE001
            if lan == so_lan - 1:
                cur.execute(
                    "SELECT usename, state, application_name FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()", (ten,))
                con_giu = cur.fetchall()
                raise AssertionError(
                    f"khong xoa duoc co so du lieu nhap {ten!r} sau {so_lan} lan thu. "
                    f"Ket noi con giu: {con_giu}. Day la RO KET NOI, khong phai "
                    f"duong dua don dep — tim cho mo ket noi ma khong dong.")
            time.sleep(0.2)


class TestBanCaiMoi:
    def test_migration_dung_len_tu_co_so_du_lieu_trong(self, csdl_trong):
        """Lượt migration THẬT, tiến trình riêng, vai tối thiểu.

        Tiến trình riêng chứ không gọi hàm: bài kiểm này phải nối tới một cơ sở
        dữ liệu KHÁC, và đổi DSN trong tiến trình đang chạy sẽ để lại nhóm kết
        nối trỏ sai cho mọi bài kiểm sau.

        Và bài kiểm KHÔNG gieo sẵn gì cả. `plans` phải do chính migration tạo
        trước khi câu gieo `community` chạy — nếu fixture tự tạo `enterprise`
        thì lỗi thứ tự sẽ bị che đúng chỗ nó cần lộ ra.
        """
        from app.storage.schema_version import APP_SCHEMA_VERSION

        mig = _dsn_doi_ten_db(
            os.environ.get("MIGRATION_DATABASE_URL")
            or os.environ["DATABASE_URL"], csdl_trong)
        app_dsn = _dsn_doi_ten_db(os.environ["DATABASE_URL"], csdl_trong)

        moi = {**os.environ,
               "MIGRATION_DATABASE_URL": mig,
               "DATABASE_URL": app_dsn,
               "EXPECTED_DATABASE": csdl_trong,
               "POSTGRES_DB": csdl_trong}
        ket_qua = subprocess.run(
            [sys.executable, "-m", "app.cli.migrate", "--to", str(APP_SCHEMA_VERSION)],
            cwd=str(REPO_ROOT / "backend"), env=moi,
            capture_output=True, text=True, timeout=900)

        assert ket_qua.returncode == 0, (
            f"migrate --to {APP_SCHEMA_VERSION} that bai tren co so du lieu "
            f"trong (ma {ket_qua.returncode}):\n"
            f"{ket_qua.stdout[-4000:]}\n{ket_qua.stderr[-4000:]}")

        import psycopg2

        # `with psycopg2.connect(...)` KHÔNG đóng kết nối — nó chỉ kết thúc giao
        # dịch. Kết nối còn sống thì lượt dọn ở `csdl_trong` phải giết chính nó,
        # và bài kiểm tự tạo ra đường đua mà nó sắp phải chịu.
        conn = psycopg2.connect(mig)
        try:
            conn.autocommit = True
            with conn.cursor() as c:
                c.execute("SELECT set_config('app.system_scope', 'on', false)")

                # Hai khẳng định NỀN, trước mọi khẳng định về nội dung.
                #
                # Lượt migration này chỉ mất ~2 giây, đủ nhanh để ngờ rằng nó
                # không chạy gì cả — hoặc tệ hơn, rằng phần kiểm bên dưới đang
                # hỏi nhầm `signdb_test`. Hai câu này phân định: `signdb_test`
                # có 63 lớp, cơ sở dữ liệu mới có 0.
                c.execute("SELECT current_database()")
                assert c.fetchone()[0] == csdl_trong

                c.execute("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
                so_bang = c.fetchone()[0]
                assert so_bang > 40, (
                    f"chi co {so_bang} bang — migration khong thuc su chay het")

                c.execute("SELECT count(*) FROM classes")
                assert c.fetchone()[0] == 0, "day KHONG phai co so du lieu trong"

                c.execute("SELECT count(*) FROM tenants WHERE tenant_id = 'default'")
                assert c.fetchone()[0] == 1, "tenant nen tang khong ra doi"

                c.execute("SELECT count(*) FROM vocabulary_registry_meta "
                          "WHERE tenant_id = 'default'")
                assert c.fetchone()[0] == 1, "dong registry meta khong ra doi"

                # Hoi theo HANG SO, khong viet cung ma tenant.
                #
                # Ngay 22/08/2026 `COMMUNITY_TENANT_ID` chuyen tu `'community'`
                # sang tenant dang giu corpus. Mot bai kiem viet cung ma cu se
                # do voi "tenant cong dong khong ra doi" — dung ve chu, sai ve
                # y: tenant cong dong CO ra doi, chi la duoi mot cai ten khac.
                from app.storage.authz_schema import COMMUNITY_TENANT_ID

                c.execute(
                    "SELECT tenant_type, is_system_reserved, slug, plan_code "
                    "FROM tenants WHERE tenant_id = %s", (COMMUNITY_TENANT_ID,))
                cd = c.fetchone()
                assert cd is not None, "tenant cong dong khong ra doi"
                assert cd[0] == "COMMUNITY"
                assert cd[1] is True
                assert cd[2] == COMMUNITY_TENANT_ID
                # Không khẳng định mã gói cụ thể — nó là trạng thái thương mại.
                # Chỉ khẳng định nó HỢP LỆ, tức lỗi `internal` không quay lại.
                assert cd[3] is not None
                c.execute("SELECT count(*) FROM plans WHERE plan_code = %s", (cd[3],))
                assert c.fetchone()[0] == 1, (
                    f"community mang plan_code={cd[3]!r} khong co trong plans")

                c.execute("SELECT count(*) FROM classes WHERE region IS NULL")
                assert c.fetchone()[0] == 0

                c.execute(
                    "SELECT attnotnull FROM pg_attribute "
                    "WHERE attrelid = 'classes'::regclass AND attname = 'region'")
                assert c.fetchone()[0] is True, "classes.region chua NOT NULL"
        finally:
            conn.close()

    def test_status_xanh_ngay_sau_lan_migrate_dau_tien(self, csdl_trong):
        """Một bản cài mới phải tự nhận là đã xong, không cần lượt chạy thứ hai."""
        from app.storage.schema_version import APP_SCHEMA_VERSION

        mig = _dsn_doi_ten_db(
            os.environ.get("MIGRATION_DATABASE_URL")
            or os.environ["DATABASE_URL"], csdl_trong)
        moi = {**os.environ,
               "MIGRATION_DATABASE_URL": mig,
               "DATABASE_URL": _dsn_doi_ten_db(os.environ["DATABASE_URL"], csdl_trong),
               "EXPECTED_DATABASE": csdl_trong,
               "POSTGRES_DB": csdl_trong}

        chay = subprocess.run(
            [sys.executable, "-m", "app.cli.migrate", "--to", str(APP_SCHEMA_VERSION)],
            cwd=str(REPO_ROOT / "backend"), env=moi,
            capture_output=True, text=True, timeout=900)
        assert chay.returncode == 0, chay.stdout[-3000:] + chay.stderr[-3000:]

        trang_thai = subprocess.run(
            [sys.executable, "-m", "app.cli.migrate", "--status"],
            cwd=str(REPO_ROOT / "backend"), env=moi,
            capture_output=True, text=True, timeout=300)
        assert trang_thai.returncode == 0, (
            f"--status khong xanh sau lan migrate dau tien:\n"
            f"{trang_thai.stdout[-3000:]}\n{trang_thai.stderr[-3000:]}")


# ---------------------------------------------------------------------------
# 4. Bất biến cấu trúc của sổ đăng ký
# ---------------------------------------------------------------------------


class TestSoDangKy:
    def test_moi_buoc_neu_ro_phien_ban_va_ten_buoc(self):
        """`reason` đi vào sổ kiểm toán, nên nó phải trả lời được "mở để làm gì".

        `"migration"` trơn thì một năm sau không ai truy được phạm vi hệ thống
        đã được mở cho việc gì.
        """
        from app.storage.metadata_db import _data_steps

        for cau, (ly_do, _, _) in _data_steps().items():
            assert re.fullmatch(r"migration:v\d+:[a-z0-9-]+", ly_do), (
                f"ly do {ly_do!r} khong dung dang migration:<phien ban>:<buoc> "
                f"(cau: {cau[:60]}…)")

    def test_moi_buoc_co_hau_dieu_kien_tra_ve_boolean(self):
        from app.storage.metadata_db import _data_steps

        for ly_do, cac_cau, hau in _data_steps().values():
            assert cac_cau, f"{ly_do}: khong co cau nao"
            assert hau.lstrip().upper().startswith("SELECT"), \
                f"{ly_do}: hau dieu kien khong phai cau SELECT"

    def test_cau_dan_dau_va_cac_cau_theo_sau_deu_nam_trong_danh_sach_that(self):
        """Sổ đăng ký khớp NGUYÊN VĂN, nên một câu trôi khỏi danh sách DDL sẽ
        lặng lẽ mất đường đặc biệt. Đây là phép kiểm bắt được điều đó."""
        from app.storage.authz_schema import AUTHZ_DDL_STATEMENTS
        from app.storage.metadata_db import (
            DDL_STATEMENTS, MIGRATION_STATEMENTS, _data_steps)

        tat_ca = set()
        for ds in (DDL_STATEMENTS, MIGRATION_STATEMENTS, AUTHZ_DDL_STATEMENTS):
            tat_ca |= {s for s in ds if isinstance(s, str)}

        for ly_do, cac_cau, _ in _data_steps().values():
            for cau in cac_cau:
                assert cau in tat_ca, (
                    f"{ly_do}: cau da dang ky khong con trong danh sach DDL nao "
                    f"— buoc nay se KHONG BAO GIO chay: {cau[:80]}…")

    def test_reader_SOT_nhan_ra_dung_nhung_cau_da_dang_ky(self, cur):
        """Sổ đăng ký và bộ đọc SOT phải nói về ĐÚNG một câu.

        `_postcondition_da_dung` khớp theo VĂN BẢN đã chuẩn hoá, nên một khoảng
        trắng lệch giữa bản chụp lược đồ đã ký và hằng số trong mã là đủ để câu
        bootstrap lặng lẽ rơi về `schema_failed` — đúng hình dạng của ba ca đỏ
        ngày 15/08/2026.

        Bộ kiểm SOT chạy qua đường này KHÔNG bắt được điều đó: chúng chỉ hỏi
        `schema_failed` rỗng hay không, nên một câu được nhận nhờ NHÁNH KHÁC
        cũng cho kết quả y hệt. Phép kiểm này hỏi câu nào được nhận nhờ nhánh
        nào.
        """
        from app.sot.catalog_schema import export_schema_sql
        from app.sot.reader_sync import (
            _postcondition_da_dung, _split_sql_statements)

        nhan = {}
        for cau in _split_sql_statements(export_schema_sql()):
            if not cau.strip().upper().startswith("INSERT"):
                continue
            ket = _postcondition_da_dung(cur, cau)
            if ket:
                nhan[ket] = " ".join(cau.split())[:70]

        assert "migration:v5:bootstrap-default-tenant" in nhan, (
            "cau bootstrap tenant goc trong ban chup KHONG khop so dang ky — "
            f"chi nhan ra: {sorted(nhan)}")
        assert "migration:v5:seed-vocabulary-registry-meta" in nhan
        # Câu này KHÔNG phải bước migration và phải ở lại `_LEGACY_SEEDS`.
        assert "legacy_seed_open_tenant_subscriptions" in nhan

    def test_plans_duoc_gieo_TRUOC_tenant_cong_dong(self):
        """Thứ tự phụ thuộc, khẳng định ở tầng cấu trúc.

        `community` mang khoá ngoại tới `plans`, nên câu gieo gói phải chạy
        trước. Hai câu nằm ở hai danh sách khác nhau và `ensure_tables()` chạy
        `MIGRATION_STATEMENTS` trước `AUTHZ_DDL_STATEMENTS` — phép kiểm này
        khoá đúng quan hệ đó lại.
        """
        from app.storage.authz_schema import (
            AUTHZ_DDL_STATEMENTS, _SQL_SEED_COMMUNITY_TENANT)
        from app.storage.metadata_db import MIGRATION_STATEMENTS

        assert any("INSERT INTO plans (" in s for s in MIGRATION_STATEMENTS
                   if isinstance(s, str))
        assert _SQL_SEED_COMMUNITY_TENANT in AUTHZ_DDL_STATEMENTS
        assert not any("INSERT INTO plans (" in s for s in AUTHZ_DDL_STATEMENTS
                       if isinstance(s, str)), (
            "cau gieo plans da chuyen sang danh sach authz — thu tu phu thuoc "
            "khong con duoc bao dam boi vi tri hai danh sach nua")
