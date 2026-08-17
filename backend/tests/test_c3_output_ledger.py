"""C3 — SỔ KIỂM KÊ đầu ra của một lượt huấn luyện.

Chạy:
    bash scripts/run_tests.sh backend/tests/test_c3_output_ledger.py -q -s

Tệp này CHƯA vá gì. Nó trả lời một câu duy nhất, bằng phép đo chứ không bằng đọc
mã: **một lượt huấn luyện để lại những gì bền vững, và mỗi thứ đó có mang tenant
không?**

Bất biến C3 sẽ khoá
===================
```
Train(T)  ->  mọi đầu ra bền vững đều thuộc T
```

Sáu mặt phẳng phải truy
=======================
```
1  hàng model registry
2  hàng model version
3  siêu dữ liệu hiện vật mô hình
4  đường dẫn lưu trữ vật lý / object store
5  hợp đồng lớp đầu ra        (C1 đã xử — vẫn kiểm để chứng minh không đứt đoạn)
6  sự kiện / webhook          (C1 đã xử — như trên)
```

Vì sao đo trước khi vá
======================
Vá từng dòng theo trí nhớ sẽ bỏ sót đúng những chỗ không ai nghĩ tới. Bài học
lặp lại nhiều lần trong đợt này: `upsert_training_job` có fallback ở **cả hai**
nhánh, và nhánh thứ hai chỉ lộ ra khi kiểm kê chứ không khi đọc.

Sổ này in ra bằng chứng ở dạng bảng để dán thẳng vào
`docs/10-issues/PROPOSAL_COMPLIANCE_MATRIX.md`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.storage.metadata_db import _migration_cursor  # noqa: E402

#: Bảng nào được coi là "đầu ra bền vững của một lượt huấn luyện".
#:
#: Danh sách này là một GIẢ THIẾT và ca đầu tiên kiểm chính nó: một bảng có
#: trong danh sách mà không tồn tại trong lược đồ nghĩa là sổ đang mô tả một hệ
#: thống khác hệ thống thật.
BANG_DAU_RA = [
    ("training_jobs", "hàng job — gốc thẩm quyền của mọi đầu ra"),
    ("training_job_classes", "hợp đồng lớp đầu ra (C1)"),
    ("training_metrics", "chỉ số từng epoch"),
]

#: Hai mặt phẳng đầu tiên của C3 — "hàng model registry" và "hàng model version"
#: — KHÔNG TỒN TẠI trong hệ thống này. Đo được, không suy ra.
#:
#: `experiments`, `experiment_metrics`, `model_versions` chỉ có DDL trong
#: `backend/migrations/001_…sql` và `002_…sql`, không có trong `ensure_tables()`;
#: `experiment_tracking_api.py` ghi vào chúng nhưng `routers/experiments.py`
#: **không được mount** (`main.py:18` nói rõ là cố ý). Không có URL nào tới được.
#:
#: Vì vậy C3 không đi tìm rò rỉ tenant ở đó — không có gì để rò. Nhưng phải ghi
#: lại, vì "chưa kiểm" và "kiểm rồi, không tồn tại" là hai trạng thái khác nhau,
#: và trạng thái thứ hai mới đóng được ô trong ma trận cam kết.
BANG_KHONG_TON_TAI = ("experiments", "experiment_metrics", "model_versions")


def _cot(cur, bang: str):
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (bang,))
    return {r[0] for r in cur.fetchall()}


def _co_bang(cur, bang: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{bang}",))
    return bool(cur.fetchone()[0])


def _rls(cur, bang: str):
    cur.execute(
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE oid = to_regclass(%s)", (f"public.{bang}",))
    r = cur.fetchone()
    return (bool(r[0]), bool(r[1])) if r else (False, False)


def _so_chinh_sach(cur, bang: str) -> int:
    cur.execute("SELECT count(*) FROM pg_policies WHERE tablename = %s", (bang,))
    return int(cur.fetchone()[0])


@pytest.fixture(scope="module")
def so():
    """Đo MỘT lần, dùng cho mọi ca — và in ra để đưa vào tài liệu."""
    ket_qua = {}
    with _migration_cursor() as cur:
        cur.execute("SELECT set_config('app.system_scope','on',false)")
        for bang, mo_ta in BANG_DAU_RA:
            if not _co_bang(cur, bang):
                ket_qua[bang] = {"ton_tai": False, "mo_ta": mo_ta}
                continue
            cot = _cot(cur, bang)
            bat, buoc = _rls(cur, bang)
            ket_qua[bang] = {
                "ton_tai": True,
                "mo_ta": mo_ta,
                "co_tenant": "tenant_id" in cot,
                "rls_bat": bat,
                "rls_force": buoc,
                "so_policy": _so_chinh_sach(cur, bang),
            }
    return ket_qua


def test_in_so_kiem_ke(so):
    """Không khẳng định gì — đây là phép ĐO, và nó phải đọc được."""
    print("\n" + "=" * 78)
    print("SỔ ĐẦU RA CỦA MỘT LƯỢT HUẤN LUYỆN — đo trên lược đồ thật")
    print("=" * 78)
    print(f"{'bảng':26} {'tenant_id':10} {'RLS':6} {'FORCE':6} {'policy':7} mô tả")
    print("-" * 78)
    for bang, v in so.items():
        if not v["ton_tai"]:
            print(f"{bang:26} {'—':10} {'—':6} {'—':6} {'—':7} KHÔNG TỒN TẠI")
            continue
        print(f"{bang:26} {str(v['co_tenant']):10} {str(v['rls_bat']):6} "
              f"{str(v['rls_force']):6} {v['so_policy']:<7} {v['mo_ta']}")
    print("=" * 78)


def test_moi_bang_trong_so_deu_ton_tai_that(so):
    """Sổ mô tả hệ thống NÀY, không phải hệ thống ta tưởng.

    Một bảng trong danh sách mà không có trong lược đồ nghĩa là sổ đã lệch khỏi
    thực tế — và một sổ lệch còn tệ hơn không có sổ, vì nó tạo cảm giác đã kiểm.
    """
    thieu = [b for b, v in so.items() if not v["ton_tai"]]
    print(f"\n[evidence] bảng không tồn tại: {thieu or 'không có'}")
    assert not thieu, (
        f"sổ nhắc tới bảng không tồn tại: {thieu}. Sửa danh sách, đừng tạo bảng.")


def test_hai_mat_phang_registry_van_KHONG_ton_tai():
    """Chốt hiệu lực cho một kết luận PHỦ ĐỊNH.

    "Không có mặt phẳng registry nên không có gì để cách ly" chỉ đúng chừng nào
    nó còn không tồn tại. Ngày ai đó mount `routers/experiments.py` hoặc chạy
    `002_mvp_schema.sql`, kết luận ấy hết hiệu lực — và ca này đỏ đúng lúc đó,
    thay vì để ma trận cam kết mang một ô đã hết hạn.
    """
    with _migration_cursor() as cur:
        cur.execute("SELECT set_config('app.system_scope','on',false)")
        co = [b for b in BANG_KHONG_TON_TAI if _co_bang(cur, b)]
    print(f"\n[evidence] bảng registry đã xuất hiện: {co or 'chưa có bảng nào'}")
    assert not co, (
        f"{co} nay đã tồn tại. Kết luận 'mặt phẳng registry không có gì để cách "
        f"ly' hết hiệu lực — phải đo lại C3 cho chúng.")


def test_liet_ke_bang_dau_ra_KHONG_co_tenant(so):
    """★ Phát hiện chính của C3, ghi ra dưới dạng số.

    Ca này KHÔNG đỏ khi tìm thấy khoảng trống — nó ghi nhận. Đỏ ở đây sẽ biến
    một phép kiểm kê thành một hàng rào, và hàng rào phải dựng sau khi đã biết
    mình đang rào cái gì.
    """
    ho = sorted(b for b, v in so.items() if v["ton_tai"] and not v["co_tenant"])
    print(f"\n[evidence] bảng đầu ra KHÔNG mang tenant_id: {json.dumps(ho, ensure_ascii=False)}")
    print(f"[evidence] tổng {len(ho)}/{len(so)} bảng")


def test_bang_co_tenant_thi_phai_co_RLS_va_FORCE(so):
    """Có cột `tenant_id` mà không có RLS là cách ly bằng quy ước.

    Quy ước dựa vào việc mọi truy vấn nhớ thêm `WHERE tenant_id = …`. Đợt này
    đã đếm được hàng chục lượt gọi quên chính mệnh đề ấy.
    """
    hong = {
        b: (v["rls_bat"], v["rls_force"], v["so_policy"])
        for b, v in so.items()
        if v["ton_tai"] and v["co_tenant"]
        and not (v["rls_bat"] and v["rls_force"] and v["so_policy"] > 0)
    }
    print(f"\n[evidence] có tenant_id nhưng RLS chưa đủ: {hong or 'không có'}")
    assert not hong, (
        f"các bảng sau mang tenant_id nhưng thiếu RLS/FORCE/policy: {hong}")
