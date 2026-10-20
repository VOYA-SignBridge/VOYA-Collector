"""Hợp đồng migration có HAI tập, không phải một.

    required_objects   phải CÓ MẶT
    retired_objects    phải VẮNG MẶT

Trước 15/08/2026 chỉ có tập thứ nhất, và hai lỗ theo sau nó:

  1. `--status` **in ra** số đối tượng thiếu nhưng không cho nó tham gia kết
     luận — một lược đồ thiếu đối tượng vẫn được báo *"khớp"*.
  2. Không có khái niệm "đối tượng đáng lẽ đã bị gỡ". Trạng thái
     `chỉ mục mới CÓ + chỉ mục cũ VẪN CÒN` được kết luận là *"khớp"*, trong khi
     lược đồ thực tế sai và biến thể vùng vẫn bị chặn.

Đo được trên `signdb` ngày 15/08: `--status` trả *"khớp — backend khởi động
được"* trong khi `uq_classes_tenant_slug_lang_dialect` vẫn còn đó và
`INSERT ăn|pho-thong|nam` vẫn bị từ chối.

Vì sao đó là lỗ TỔNG QUÁT chứ không phải một chỉ mục xui xẻo
------------------------------------------------------------
Câu `DROP` nằm trong danh sách một chiều nên KHÔNG chạy lúc khởi động — đúng
thiết kế. Nhưng câu `CREATE` của chính chỉ mục đó thì lại chạy MỌI lần khởi
động. Migration bỏ nó, backend khởi động lại dựng nó lên nguyên vẹn. Không có
gì trong khung migration phát hiện được vòng lặp đó.

Nên `retired_indexes()` được SUY RA từ chính các câu DDL — bị một câu một chiều
bỏ, và không được tạo lại ở đâu — chứ không liệt kê tay. Liệt kê tay chỉ mạnh
bằng trí nhớ của người viết, và chính lần này đã chứng minh trí nhớ đó hụt.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.storage import metadata_db as db  # noqa: E402

CHI_MUC_CU = "uq_classes_tenant_slug_lang_dialect"
CHI_MUC_MOI = "uq_classes_tenant_slug_lang_dialect_region"


class TestSuyRaDoiTuongDaRetire:
    def test_danh_sach_khong_rong_va_co_chi_muc_da_biet(self):
        """Chốt hiệu lực. Rỗng nghĩa là phép kiểm không canh gì cả."""
        ten = db.retired_indexes()

        assert ten, "không suy ra được đối tượng retire nào — phép kiểm thành vô hiệu"
        assert CHI_MUC_CU in ten

    def test_chi_muc_bi_bo_ROI_TAO_LAI_khong_tinh_la_retire(self):
        """Phân biệt RETIRE với THAY THẾ, và khác biệt này là bắt buộc.

        `uq_classes_..._region` cũng có một câu DROP: bản `coalesce(region,'')`
        cũ phải bị bỏ trước khi dựng bản trần, vì `CREATE ... IF NOT EXISTS`
        lặng lẽ KHÔNG thay thế một chỉ mục cùng tên có định nghĩa khác.

        Nếu suy ra "retire" chỉ từ câu DROP thì chỉ mục này bị coi là đã retire,
        và `--status` sẽ báo lỗi trên MỌI cơ sở dữ liệu đúng.
        """
        assert CHI_MUC_MOI not in db.retired_indexes()

    def test_cau_TAO_chi_muc_cu_da_duoc_GO_khoi_luoc_do(self):
        """Bài học 14/08: thêm câu xoá là CHƯA ĐỦ, phải gỡ câu tạo.

        Đây là ca canh trực tiếp cho vòng lặp `migration bỏ → khởi động dựng
        lại`. Ai đó thêm lại câu `CREATE` sẽ làm ca này đỏ, thay vì để lỗi hiện
        ra dưới dạng "biến thể vùng bị chặn" vài tuần sau.
        """
        cau_tao = [s for s in db._all_schema_statements()
                   if db._RE_CREATE_INDEX.match(s)
                   and db._RE_CREATE_INDEX.match(s).group(1).lower() == CHI_MUC_CU]

        assert cau_tao == [], (
            f"câu CREATE của {CHI_MUC_CU} vẫn còn trong lược đồ — migration sẽ bỏ "
            f"nó rồi lần khởi động kế tiếp dựng lại, và không ai được báo")

    def test_cau_TAO_chi_muc_MOI_van_con(self):
        """Ngược chiều: bản có `region` phải còn được tạo."""
        cau_tao = [s for s in db._all_schema_statements()
                   if db._RE_CREATE_INDEX.match(s)
                   and db._RE_CREATE_INDEX.match(s).group(1).lower() == CHI_MUC_MOI]

        assert len(cau_tao) == 1


class TestBieuThucChinhQuy:
    """Bộ dò tên chỉ mục phải chịu được các biến thể cú pháp thật."""

    @pytest.mark.parametrize("cau,ten", [
        ("DROP INDEX IF EXISTS abc", "abc"),
        ("DROP INDEX abc", "abc"),
        ("drop index concurrently if exists abc", "abc"),
        ("  DROP INDEX IF EXISTS abc  ", "abc"),
    ])
    def test_bat_duoc_cau_drop(self, cau, ten):
        m = db._RE_DROP_INDEX.match(cau)
        assert m and m.group(1) == ten

    @pytest.mark.parametrize("cau,ten", [
        ("CREATE UNIQUE INDEX IF NOT EXISTS abc ON t(x)", "abc"),
        ("CREATE INDEX abc ON t(x)", "abc"),
        ("create unique index concurrently abc ON t(x)", "abc"),
    ])
    def test_bat_duoc_cau_create(self, cau, ten):
        m = db._RE_CREATE_INDEX.match(cau)
        assert m and m.group(1) == ten

    def test_khong_bat_nham_cau_khac(self):
        for cau in ("DROP TABLE abc", "ALTER TABLE t DROP COLUMN c",
                    "CREATE TABLE abc (x int)"):
            assert db._RE_DROP_INDEX.match(cau) is None
            assert db._RE_CREATE_INDEX.match(cau) is None


@pytest.mark.integration
class TestDuongNangCap:
    """Không chỉ "lược đồ mới dựng đúng" — mà "lược đồ CŨ nâng cấp được".

    Hai kiểu kiểm khác nhau, và chỉ kiểu thứ hai bảo vệ được lỗi thật:

        A. cơ sở dữ liệu trắng  → lược đồ hiện hành
        B. lược đồ TRƯỚC region → migrate → lược đồ hiện hành   ← ở đây

    Kiểu A luôn xanh kể cả khi câu retire chạy hụt, vì trên một cơ sở dữ liệu
    trắng thì chỉ mục cũ chưa từng tồn tại để mà sót lại.
    """

    @pytest.fixture
    def truoc_region(self):
        """Dựng lại trạng thái TRƯỚC khi `region` vào định danh, rồi dọn sạch.

        `finally` là bắt buộc: ca này ghi vào cơ sở dữ liệu test dùng chung, và
        một chỉ mục sót lại sẽ chặn mọi ca khác cần biến thể vùng.
        """
        from app.storage.metadata_db import _migration_cursor

        with _migration_cursor() as cur:
            cur.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {CHI_MUC_CU} "
                f"ON classes(tenant_id, slug, language, dialect) "
                f"WHERE deleted_at IS NULL")
        try:
            yield
        finally:
            with _migration_cursor() as cur:
                cur.execute(f"DROP INDEX IF EXISTS {CHI_MUC_CU}")

    def _co_chi_muc(self, ten: str) -> bool:
        from app.storage.metadata_db import _migration_cursor

        with _migration_cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_indexes WHERE schemaname = current_schema() "
                "AND indexname = %s", (ten,))
            return cur.fetchone() is not None

    def test_phat_hien_duoc_truoc_khi_migrate(self, truoc_region):
        """Nếu không phát hiện được thì `--status` vẫn sẽ nói dối."""
        from app.storage.metadata_db import _migration_cursor, retired_still_present

        with _migration_cursor() as cur:
            con_sot = retired_still_present(cur)

        assert any(CHI_MUC_CU in s for s in con_sot), con_sot

    def test_migrate_go_chi_muc_cu_va_GIU_chi_muc_moi(self, truoc_region):
        from app.storage.metadata_db import _migration_cursor, migrate_database

        assert self._co_chi_muc(CHI_MUC_CU), "fixture chưa dựng được trạng thái cũ"

        migrate_database(note="test: đường nâng cấp trước-region", stamp=False)

        assert not self._co_chi_muc(CHI_MUC_CU), (
            "migration KHÔNG gỡ được chỉ mục cũ — đường nâng cấp hỏng")
        assert self._co_chi_muc(CHI_MUC_MOI), (
            "gỡ mất luôn chỉ mục có region — còn tệ hơn không gỡ gì")

        with _migration_cursor() as cur:
            assert retired_con_sot(cur) == [], "vẫn còn đối tượng đáng lẽ đã gỡ"

    def test_sau_migrate_hai_bien_the_vung_vao_duoc(self, truoc_region):
        """Bằng chứng NGHIỆP VỤ, không chỉ bằng chứng về catalog.

        Chỉ mục biến mất là điều kiện; điều thật sự cần là hai biến thể miền
        của cùng một từ cùng tồn tại được, và bản trùng thật thì vẫn bị chặn.
        """
        from app.storage.metadata_db import _execute, _fetch_all, migrate_database
        from app.tenant_context import system_scope

        migrate_database(note="test: đường nâng cấp trước-region", stamp=False)

        # Ghi qua vai ỨNG DỤNG, không qua vai migration: `classes` bật RLS và
        # vai DDL không có chính sách nào cho phép ghi. Kiểm bằng vai sai sẽ
        # đỏ vì một lý do chẳng liên quan gì tới chỉ mục đang xét.
        uids = ["MG-BAC", "MG-NAM", "MG-DUP"]
        THEM = ("INSERT INTO classes(tenant_id, class_uid, slug, label_original, "
                "language, dialect, region) "
                "VALUES('default', %s, 'an-migrate', 'an', 'vn', 'common', %s)")
        try:
            with system_scope("test: đường nâng cấp"):
                for uid, vung in (("MG-BAC", "bac"), ("MG-NAM", "nam")):
                    _execute(THEM, (uid, vung))

                dem = _fetch_all(
                    "SELECT count(*) AS n FROM classes WHERE slug = 'an-migrate' "
                    "AND deleted_at IS NULL")[0]["n"]
                assert int(dem) == 2, "hai biến thể vùng KHÔNG cùng vào được"

                # Bản trùng thật vẫn phải bị chặn — nới quá tay cũng là hỏng.
                with pytest.raises(Exception) as loi:
                    _execute(THEM, ("MG-DUP", "bac"))
                assert CHI_MUC_MOI in str(loi.value), str(loi.value)[:200]
        finally:
            with system_scope("test cleanup"):
                _execute("DELETE FROM classes WHERE class_uid = ANY(%s)", (uids,))


def retired_con_sot(cur):
    from app.storage.metadata_db import retired_still_present

    return retired_still_present(cur)
