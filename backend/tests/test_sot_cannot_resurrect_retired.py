"""Một gói SOT đã ký KHÔNG được hồi sinh đối tượng mà migration đã retire.

Sự cố 15/08/2026, tìm ra bằng chính phép kiểm-lại-sau-khi-bật vừa thêm vào
`deploy.sh`:

    migrate --status  TRUOC up -d  -> khop, con sot 0
    up -d  (sot_init chay)
    migrate --status  SAU  up -d  -> KHONG KHOP, con sot 1
                                     uq_classes_tenant_slug_lang_dialect

Gói `Ver5_06082026` — chữ ký hợp lệ, không hề bị sửa — được publish TRƯỚC khi
`region` bước vào định danh lớp. `catalog_schema.export_schema_sql()` chụp lược
đồ tại thời điểm ấy và nhúng vào gói, nên gói mang nguyên văn:

    CREATE UNIQUE INDEX IF NOT EXISTS uq_classes_tenant_slug_lang_dialect …

và KHÔNG mang bản có `region`. `reader_sync` phát lại toàn bộ ở MỖI lượt sync,
nên `migrate` gỡ chỉ mục rồi `sot_init` dựng lại ngay trong cùng lượt triển khai.

Điều phép kiểm cũ hỏi và điều nó KHÔNG hỏi
------------------------------------------
Chữ ký hợp lệ chứng minh gói **không bị sửa**. Nó không chứng minh nội dung còn
**đúng với hệ thống hôm nay**. Hai câu hỏi khác nhau, và trước hôm nay chỉ câu
thứ nhất được hỏi.

Bất biến được khoá ở đây
------------------------
    Một hiện vật lịch sử được phép MÔ TẢ lược đồ của thời điểm nó ra đời, nhưng
    không được vượt quyền migration để khôi phục thứ hệ thống hiện hành đã
    retire.

Và danh sách retire phải là DUY NHẤT: `metadata_db.creates_retired_object()`,
cùng nguồn `migrate --status` dùng. Một danh sách thứ hai nằm bên SOT sẽ trôi
khỏi nó đúng như mọi danh sách chép tay khác đã trôi.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dataset_manager import REGION_UNCLASSIFIED  # noqa: E402
from app.storage import metadata_db as db  # noqa: E402

CHI_MUC_CU = "uq_classes_tenant_slug_lang_dialect"
CHI_MUC_MOI = "uq_classes_tenant_slug_lang_dialect_region"

#: Chép nguyên văn hình dạng câu nằm trong gói `Ver5_06082026` thật.
DDL_CU = (
    f"CREATE UNIQUE INDEX IF NOT EXISTS {CHI_MUC_CU} "
    f"ON classes(tenant_id, slug, language, dialect) WHERE deleted_at IS NULL"
)
#: Câu vô hại, để chứng minh chốt chặn KHÔNG chặn nhầm phần còn lại.
CHI_MUC_THU = "idx_sot_guard_probe"
DDL_VO_HAI = f"CREATE INDEX IF NOT EXISTS {CHI_MUC_THU} ON classes(created_at)"


class TestNhanDienDoiTuongDaRetire:
    """Tầng đầu: nhận diện đúng đối tượng mà một câu định TẠO."""

    def test_bat_duoc_cau_dung_lai_chi_muc_da_retire(self):
        assert db.creates_retired_object(DDL_CU) == CHI_MUC_CU

    def test_khong_bat_nham_ban_co_region(self):
        """Bản có `region` là trạng thái ĐÍCH — chặn nó là tự phá lược đồ."""
        cau = (f"CREATE UNIQUE INDEX IF NOT EXISTS {CHI_MUC_MOI} "
               f"ON classes(tenant_id, slug, language, dialect, region)")
        assert db.creates_retired_object(cau) is None

    def test_khong_bat_nham_cau_thuong(self):
        for cau in (DDL_VO_HAI, "CREATE TABLE IF NOT EXISTS x (a int)",
                    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS z text",
                    "DROP INDEX IF EXISTS " + CHI_MUC_CU):
            assert db.creates_retired_object(cau) is None, cau

    def test_dung_CHUNG_nguon_voi_migrate_status(self):
        """Không có danh sách thứ hai. Đây là chốt chặn cho chính điều đó.

        Nếu ai đó thêm một danh sách retire riêng cho SOT, hai bên sẽ trôi khỏi
        nhau và lỗi quay lại y hệt — chỉ khác là lần sau sẽ khó tìm hơn, vì
        `migrate --status` vẫn xanh.
        """
        assert CHI_MUC_CU in db.retired_indexes()
        assert db.creates_retired_object(DDL_CU) in db.retired_indexes()


@pytest.mark.integration
class TestPhatLaiKhongDungLaiDuocChiMuc:
    """Tầng hai: chạy thật `_apply_schema_sql` lên cơ sở dữ liệu test."""

    @pytest.fixture(autouse=True)
    def don_dep(self):
        """Dọn SAU, luôn luôn.

        Nếu một ca đỏ mà chỉ mục cũ còn nằm lại thì nó chặn mọi ca khác cần
        biến thể vùng — một lỗi lan sang chỗ chẳng liên quan.
        """
        yield
        from app.storage.metadata_db import _migration_cursor

        with _migration_cursor() as cur:
            cur.execute(f"DROP INDEX IF EXISTS {CHI_MUC_CU}")
            cur.execute(f"DROP INDEX IF EXISTS {CHI_MUC_THU}")

    def _co(self, ten: str) -> bool:
        from app.storage.metadata_db import _migration_cursor

        with _migration_cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_indexes WHERE schemaname = current_schema() "
                "AND indexname = %s", (ten,))
            return cur.fetchone() is not None

    def test_cau_dung_lai_doi_tuong_retire_KHONG_duoc_chay(self):
        from app.sot.reader_sync import _apply_schema_sql

        assert not self._co(CHI_MUC_CU), "moi truong ban truoc khi kiem"

        bao_cao = _apply_schema_sql(DDL_CU + ";")

        assert not self._co(CHI_MUC_CU), (
            "goi SOT da dung lai duoc chi muc DA RETIRE — bien the vung bi chan lai")
        assert bao_cao.skipped_retired == [CHI_MUC_CU]
        assert bao_cao.applied == 0
        assert bao_cao.failed == []

    def test_phan_con_lai_VAN_duoc_ap(self):
        """Chốt chặn phải hẹp. Chặn cả gói thì reader thành vô dụng."""
        from app.sot.reader_sync import _apply_schema_sql

        bao_cao = _apply_schema_sql(f"{DDL_CU};\n{DDL_VO_HAI};")

        assert not self._co(CHI_MUC_CU)
        assert self._co(CHI_MUC_THU), "cau vo hai bi chan oan"
        assert bao_cao.applied == 1
        assert bao_cao.skipped_retired == [CHI_MUC_CU]

    def test_that_bai_ngoai_du_kien_KHONG_bi_nuot(self):
        """Bỏ-theo-chính-sách và HỎNG là hai chuyện, không được trộn.

        Bản trước ghi mọi thất bại ở mức warning rồi trả về "applied", nên một
        lượt phát lại hỏng nửa chừng đọc lên y hệt một lượt sạch.
        """
        from app.sot.reader_sync import _apply_schema_sql

        bao_cao = _apply_schema_sql("CREATE INDEX zzz ON bang_khong_ton_tai(x);")

        assert bao_cao.applied == 0
        assert bao_cao.skipped_retired == []
        assert len(bao_cao.failed) == 1
        assert "bang_khong_ton_tai" in bao_cao.failed[0]


@pytest.mark.integration
class TestVangMatKhacNullTuongMinh:
    """Quy tắc tương thích ngược TỔNG QUÁT, `region` chỉ là ca đầu tiên.

        KHÔNG CÓ TRƯỜNG  =  hiện vật không biết chiều thông tin này
                         ≠  NULL tường minh
                         ≠  đặt lại giá trị đang có

    Gói `Ver5_06082026` publish trước khi cột `region` ra đời, nên `labels.csv`
    của nó không có cột ấy. Trước 15/08/2026 `upsert_class` đọc sự vắng mặt đó
    thành `None` và `SQL_UPSERT_CLASS` thậm chí không có cột `region` — nên
    `signdb_test` tích lại 63/63 lớp `region` NULL, và vì thế
    `ALTER COLUMN region SET NOT NULL` không bao giờ chạy được. Một vòng tự nuôi
    mình: gói cũ ghi NULL → NOT NULL hỏng → cột vẫn nhận NULL.

    `COALESCE` trong SQL chỉ nhìn thấy NULL, nên nếu tầng ứng dụng không tách ba
    trạng thái ra thì "không biết" và "cố ý xoá" nhập làm một — và cái sau lặng
    lẽ được đối xử như "giữ nguyên".
    """

    UID = "SOTCOMPAT_region"

    @pytest.fixture(autouse=True)
    def don_dep(self):
        yield
        from app.storage.metadata_db import _execute
        from app.tenant_context import system_scope

        with system_scope("test cleanup"):
            _execute("DELETE FROM classes WHERE class_uid = %s", (self.UID,))

    def _tao(self, **them):
        from app.storage.metadata_db import upsert_class
        from app.tenant_context import system_scope

        hang = {"class_uid": self.UID, "slug": "compat-vung", "label_original": "x",
                "language": "vn", "dialect": "common"}
        hang.update(them)
        with system_scope("test"):
            upsert_class(hang)

    def _vung(self):
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import system_scope

        with system_scope("test"):
            r = _fetch_all("SELECT region FROM classes WHERE class_uid = %s", (self.UID,))
        return r[0]["region"] if r else None

    def test_tao_moi_KHONG_co_khoa_region_thi_unclassified(self):
        self._tao()
        assert self._vung() == REGION_UNCLASSIFIED

    def test_tao_moi_region_NULL_tuong_minh_thi_TU_CHOI(self):
        with pytest.raises(ValueError, match="NULL tường minh"):
            self._tao(region=None)

    def test_hien_vat_cu_KHONG_co_khoa_region_thi_GIU_NGUYEN(self):
        """Ca đắt nhất: đúng thứ gói Ver5 làm với 60 lớp `nam` của sản xuất."""
        self._tao(region="nam")
        assert self._vung() == "nam"

        self._tao()  # gói cũ gửi lại, không mang cột `region`

        assert self._vung() == "nam", (
            "hien vat cu da xoa vung — mot goi publish truoc khi cot ra doi vua "
            "go bo cong phan loai vung")

    def test_o_TRONG_cua_CSV_cung_la_vang_mat(self):
        """CSV không phân biệt được 'không có cột' với 'ô để trống'."""
        self._tao(region="nam")
        self._tao(region="")
        assert self._vung() == "nam"

    def test_NULL_tuong_minh_tren_lop_DA_CO_van_bi_TU_CHOI(self):
        """Không được rơi vào 'giữ nguyên'. Đó là hai ngữ nghĩa khác nhau."""
        self._tao(region="nam")
        with pytest.raises(ValueError, match="NULL tường minh"):
            self._tao(region=None)
        assert self._vung() == "nam", "da tu choi ma van ghi"

    def test_noi_RO_vung_thi_ghi_duoc(self):
        """Chốt chặn không được đi quá tay: hiện vật BIẾT vùng thì phải ghi."""
        self._tao(region="nam")
        self._tao(region="bac")
        assert self._vung() == "bac"


@pytest.mark.integration
class TestGoiKySachVanKhongVuotQuyen:
    """Tầng ba: gói THẬT, ký thật, đi qua đúng đường `sync_from_sot`."""

    @pytest.fixture
    def goi_mang_ddl_cu(self, tmp_path):
        """Publish một gói HỢP LỆ nhưng mang DDL đời cũ.

        Chữ ký đúng, manifest khớp, checksum khớp — không có gì để từ chối.
        Đó chính là điều làm lỗi này khó thấy: gói KHÔNG hỏng.
        """
        from app.sot import keys
        from app.sot.publisher import publish_version
        from app.sot.store import LocalSotStore

        authz = tmp_path / "authorized_keys.json"
        authz.write_text("[]", encoding="utf-8")
        key_path = tmp_path / "may.key"
        pk = keys.generate_private_key()
        keys.save_private_key(pk, key_path)
        keys.add_authorized_key("may-cu", keys.public_key_b64(pk), authz)

        store = LocalSotStore(tmp_path / "SOT")
        publish_version(
            store,
            csv_sources={
                "labels.csv": b"class_uid,slug\n",
                "samples.csv": b"sample_uid,class_uid\n",
                "raw_uploads.csv": b"upload_uid,class_uid\n",
            },
            schema_sql=f"{DDL_CU};\n{DDL_VO_HAI};",
            schema_version=5,
            required_columns={"classes": ["class_uid"]},
            machine_name="may-cu",
            private_key_path=key_path,
            authorized_keys_path=authz,
        )
        yield store, keys.load_authorized_keys(authz)

        from app.storage.metadata_db import _migration_cursor

        with _migration_cursor() as cur:
            cur.execute(f"DROP INDEX IF EXISTS {CHI_MUC_CU}")
            cur.execute(f"DROP INDEX IF EXISTS {CHI_MUC_THU}")

    def test_sync_nhan_goi_nhung_KHONG_dung_lai_chi_muc(self, goi_mang_ddl_cu):
        from app.sot.reader_sync import CatalogSink, _apply_schema_sql, sync_from_sot
        from app.storage import metadata_db as mdb
        from app.storage.metadata_db import _migration_cursor

        store, authorized = goi_mang_ddl_cu
        sink = CatalogSink(
            apply_schema=_apply_schema_sql,
            column_exists=mdb._column_exists,
            count_rows=lambda t: mdb._fetch_all(f"SELECT COUNT(*) AS c FROM {t}")[0]["c"],
            upsert_class=mdb.upsert_class,
            upsert_sample=mdb.upsert_sample,
            upsert_raw_upload=mdb.upsert_raw_upload,
        )

        ket_qua = sync_from_sot(store, sink, authorized_keys=authorized)

        # Gói hợp lệ nên sync PHẢI nhận — chốt chặn này không phải phép từ chối.
        assert ket_qua.status == "applied", ket_qua.reason
        assert ket_qua.signed_by == "may-cu"
        assert ket_qua.schema_skipped_retired == [CHI_MUC_CU]

        with _migration_cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_indexes WHERE schemaname = current_schema() "
                "AND indexname = %s", (CHI_MUC_CU,))
            assert cur.fetchone() is None, (
                "chi muc DA RETIRE song lai tu mot goi SOT hop le")
            assert mdb.retired_still_present(cur) == []
