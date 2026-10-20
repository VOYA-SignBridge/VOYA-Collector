"""Mẫu thu được phải ghi vào tenant của LỚP, không rơi về tenant khởi tạo.

Hai mặt phẳng cách ly nói cùng một chuyện, hoặc không nói gì cả
---------------------------------------------------------------
Hệ thống cách ly dữ liệu ở hai chỗ độc lập:

* **mặt phẳng tệp** — `ClassMetadata.hierarchy_path()` gọi
  `tenant_features_root(self.tenant_id)`, nên tệp `.npz` của tenant X nằm dưới
  `_tenants/X/...`;
* **mặt phẳng siêu dữ liệu** — dòng trong `samples.csv` và trong Postgres, lọc
  bằng RLS theo cột `tenant_id`.

`save_sequence_npz` nhận `class_meta` (CÓ `tenant_id`) nhưng không chép giá trị
ấy vào dòng nó dựng. `append_sample_row` gọi `tenant_id_of(row)`, không thấy
khoá nào, và rơi về `DEFAULT_TENANT_ID` — theo đúng thiết kế của hàm chuẩn hoá,
vốn tồn tại để phục vụ những dòng CSV có TRƯỚC khi tenant ra đời.

Hệ quả: tệp nằm ở `_tenants/X/`, còn dòng dữ liệu ghi là của `default`. Hai mặt
phẳng chỉ vào hai nơi khác nhau cho cùng một mẫu, và nó hỏng theo CẢ HAI hướng:

* tenant X không thấy mẫu của chính mình — RLS lọc mất;
* tenant khởi tạo THẤY một dòng trỏ vào tệp thuộc tenant X.

Không lộ ra trên máy đang chạy vì ở đó chỉ `default` có dữ liệu, và các test
cách ly chèn thẳng vào bảng nên không đi qua đường thu mẫu.
"""

from __future__ import annotations

import uuid

import numpy as np
import pytest

from app.tenancy import DEFAULT_TENANT_ID, TENANT_COLUMN


@pytest.fixture
def lop_cua_tenant_khac():
    """`ClassMetadata` thuộc một tenant KHÁC tenant khởi tạo."""
    from app.dataset_manager import ClassMetadata

    tag = uuid.uuid4().hex[:8]
    return ClassMetadata(
        class_uid=f"captest_{tag}",
        class_idx=1,
        slug=f"captest-{tag}",
        label_original="lop cua to chuc",
        language="vn",
        dialect="common",
        is_common_global=False,
        is_common_language=False,
        tenant_id="truong-xyz",
    )


@pytest.fixture
def bat_dong_ghi(monkeypatch):
    """Chặn mọi tác dụng phụ, chỉ giữ lại DÒNG mà hàm định ghi.

    Không chạm đĩa và không chạm cơ sở dữ liệu: điều đang kiểm là hình dạng của
    dòng, không phải việc ghi tệp có chạy không.
    """
    from app import dataset_samples as ds

    bat: dict = {}
    monkeypatch.setattr(ds, "append_sample_row", lambda row: bat.update(csv=dict(row)))
    monkeypatch.setattr(ds, "_atomic_write_npz", lambda *a, **k: None)
    monkeypatch.setattr(ds, "atomic_write_json", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.storage.metadata_db.insert_sample", lambda row: bat.update(db=dict(row)))
    return bat


def _thu_mot_mau(class_meta, meta=None):
    from app.dataset_samples import save_sequence_npz

    seq = np.zeros((60, 126), dtype=np.float32)
    return save_sequence_npz(class_meta, seq, meta=meta or {}, augment_id=0,
                             source_type="camera")


class TestTenantDiTheoLop:
    def test_dong_CSV_mang_tenant_cua_lop(self, lop_cua_tenant_khac, bat_dong_ghi):
        """Đây là phép khẳng định trung tâm của tệp này."""
        _thu_mot_mau(lop_cua_tenant_khac)

        row = bat_dong_ghi.get("csv")
        assert row is not None, "khong bat duoc dong CSV nao"
        assert row.get(TENANT_COLUMN) == "truong-xyz", (
            f"mau thu cho lop cua 'truong-xyz' lai ghi tenant "
            f"{row.get(TENANT_COLUMN)!r}. Tep .npz nam duoi _tenants/truong-xyz/ "
            f"nhung dong du lieu thi khong — hai mat phang cach ly da lech nhau."
        )

    def test_dong_Postgres_mang_cung_tenant_ay(self, lop_cua_tenant_khac, bat_dong_ghi):
        """Bản sao trong Postgres phải kể cùng câu chuyện với CSV.

        `insert_sample` chạy `optional_tenant_id(...)`, và một khoá vắng mặt trở
        thành `NULL`, rồi `SQL_UPSERT_SAMPLE` thay `NULL` bằng tenant khởi tạo.
        Nên bỏ khoá này ở đây không tạo ra lỗi nào — nó tạo ra một phân vùng
        sai, im lặng.
        """
        _thu_mot_mau(lop_cua_tenant_khac)

        row = bat_dong_ghi.get("db")
        assert row is not None, "khong bat duoc dong Postgres nao"
        assert row.get(TENANT_COLUMN) == "truong-xyz"

    def test_hai_dong_khong_duoc_lech_nhau(self, lop_cua_tenant_khac, bat_dong_ghi):
        """Nguồn sự thật và bản sao phải khớp.

        Kiểm riêng, vì hai dict được dựng ở hai chỗ khác nhau trong cùng một hàm
        — đúng kiểu chỗ mà một lần sửa chỉ chạm một bên.
        """
        _thu_mot_mau(lop_cua_tenant_khac)

        assert bat_dong_ghi["csv"].get(TENANT_COLUMN) == \
            bat_dong_ghi["db"].get(TENANT_COLUMN)

    def test_lop_cua_tenant_khoi_tao_van_ghi_dung(self, bat_dong_ghi):
        """Đối chứng: bản vá không được đổi hành vi của tenant khởi tạo.

        Không có bài này, một bản vá viết cứng `"truong-xyz"` cũng xanh.
        """
        from app.dataset_manager import ClassMetadata

        tag = uuid.uuid4().hex[:8]
        goc = ClassMetadata(
            class_uid=f"captest_{tag}", class_idx=1, slug=f"captest-{tag}",
            label_original="lop goc", language="vn", dialect="common",
            is_common_global=False, is_common_language=False,
        )
        _thu_mot_mau(goc)

        assert bat_dong_ghi["csv"].get(TENANT_COLUMN) == DEFAULT_TENANT_ID
