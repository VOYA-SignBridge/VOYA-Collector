"""SOT có "hoạt động theo workspace" không — phép kiểm cho Kết quả 7 của proposal.

CHƯA CHẠY LẦN NÀO. Viết trong lúc full suite đang chạy trên `signdb_test`; chạy
bằng `sh scripts/run_tests.sh backend/tests/test_sot_tenant_scope.py -q`.

Điều đang được kiểm
===================
Proposal cam kết: *"Signed, versioned data-integrity and synchronization
mechanism (Source-of-Truth) **operating per workspace**"*. Câu đó gộp ba mệnh đề
rất khác nhau, và chúng có thể đúng sai độc lập:

    (1) mỗi dòng trong gói mang đúng tenant chủ sở hữu
    (2) một gói publish là gói CỦA MỘT workspace
    (3) cơ chế thu phạm vi theo workspace là khả thi

`test_tenant_sot_column.py` đã phủ (1) ở mức cột và mức "vắng mặt khác mặc định".
Tệp này phủ (2) và (3), tức là phủ đúng chỗ câu chữ của proposal dễ sai nhất.

Vì sao (2) đáng ngờ trước khi chạy
-----------------------------------
`sot/cli.py::_gather_csv_sources()` chạy

    SELECT {cols} FROM classes WHERE deleted_at IS NULL ORDER BY ...

**không có mệnh đề tenant, và không có khối thu phạm vi nào bao quanh.** Nghĩa là
nó trả về đúng những gì phạm vi của kết nối cho phép thấy. Dưới phạm vi hệ thống
— cách CLI vẫn chạy — đó là MỌI tenant.

Nếu `test_goi_publish_la_toan_nen_tang` xanh thì gói SOT **không** phải gói theo
workspace, và câu trong proposal phải sửa thành: *các dòng mang phạm vi tenant
bên trong một gói ký toàn nền tảng*. Đó là một mệnh đề hẹp hơn nhưng đúng, và vẫn
đủ để bảo vệ tính toàn vẹn xuyên triển khai.

Test này được viết để **ghim hành vi thật**, không để chứng minh một câu quảng
cáo. Nếu một ngày SOT được đóng gói theo workspace thật thì chính test này phải
đỏ, và đó là lúc sửa cả nó lẫn câu trong quyển.
"""

from __future__ import annotations

import csv
import io
import uuid

import pytest


def _gather() -> dict:
    from app.sot.cli import _gather_csv_sources

    return _gather_csv_sources()


def _rows(package: dict, filename: str) -> list[dict]:
    blob = package[filename]
    text = blob.decode("utf-8") if isinstance(blob, (bytes, bytearray)) else blob
    return list(csv.DictReader(io.StringIO(text)))


def _make_class(tenant_id: str, slug: str) -> str:
    """Một lớp từ vựng thuộc `tenant_id`. Trả về `class_uid`.

    Ghi thẳng qua tầng lưu trữ chứ không qua HTTP: phép kiểm này nói về nội dung
    gói SOT, không nói về đường API, và đi qua router sẽ kéo theo xác thực,
    phân quyền và hạn mức — ba thứ có thể đỏ vì lý do chẳng liên quan gì.
    """
    from app.storage import metadata_db as db
    from app.tenant_context import tenant_scope

    class_uid = uuid.uuid4().hex[:16]
    with tenant_scope(tenant_id):
        db._execute(
            "INSERT INTO classes(class_uid, tenant_id, slug, label_original, language) "
            "VALUES(%s, %s, %s, %s, 'vn')",
            (class_uid, tenant_id, slug, slug),
        )
    return class_uid


@pytest.fixture()
def hai_tenant():
    """Hai tenant sạch, tự dọn. Hai chứ không một: mọi mệnh đề ở đây là mệnh đề
    SO SÁNH, và một tenant duy nhất thì không phân biệt được "giữ đúng chủ sở
    hữu" với "gán mọi thứ cho tenant đang chạy"."""
    from app import tenant_admin
    from conftest import purge_tenant

    a = f"sota{uuid.uuid4().hex[:8]}"
    b = f"sotb{uuid.uuid4().hex[:8]}"
    for t in (a, b):
        tenant_admin.create_tenant(
            t, display_name=f"SOT scope {t}", clone_catalog=False
        )
    yield a, b
    for t in (a, b):
        purge_tenant(t)


def test_moi_dong_mang_dung_tenant_chu_so_huu(hai_tenant):
    """(1) Lớp của A không bao giờ xuất hiện dưới tenant của B.

    Đây là mệnh đề load-bearing thật sự: một máy nhận gói sẽ upsert theo
    `tenant_id` trong CSV, nên một dòng mang sai tenant là chuyển quyền sở hữu
    dữ liệu **im lặng** trên máy đích.
    """
    a, b = hai_tenant
    ua = _make_class(a, f"lop-cua-a-{uuid.uuid4().hex[:6]}")
    ub = _make_class(b, f"lop-cua-b-{uuid.uuid4().hex[:6]}")

    rows = {r["class_uid"]: r for r in _rows(_gather(), "labels.csv")}

    assert ua in rows, "lớp của A không có trong gói publish"
    assert ub in rows, "lớp của B không có trong gói publish"
    assert rows[ua]["tenant_id"] == a
    assert rows[ub]["tenant_id"] == b
    # Đối chứng âm, và nó không thừa: một lỗi gán mặc định sẽ làm CẢ HAI dòng
    # mang cùng một tenant, và hai khẳng định bên trên vẫn có thể xanh nếu
    # `a == b` vì một lỗi ở fixture.
    assert a != b
    assert rows[ua]["tenant_id"] != rows[ub]["tenant_id"]


def test_goi_publish_la_toan_nen_tang_chu_khong_theo_workspace(hai_tenant):
    """(2) GHIM GIỚI HẠN: một gói chứa dòng của nhiều tenant.

    Test này **mong đợi hành vi hiện tại**, không mong đợi hành vi lý tưởng. Nó
    tồn tại để không ai viết "gói SOT theo từng workspace" vào quyển luận văn
    khi điều đó chưa đúng.

    Ngày SOT được đóng gói theo workspace thật, test này phải đỏ — và cái đỏ đó
    là tín hiệu sửa câu chữ trong quyển, không phải tín hiệu sửa test.
    """
    a, b = hai_tenant
    _make_class(a, f"lop-a-{uuid.uuid4().hex[:6]}")
    _make_class(b, f"lop-b-{uuid.uuid4().hex[:6]}")

    tenants = {r["tenant_id"] for r in _rows(_gather(), "labels.csv")}

    assert {a, b} <= tenants, "gói phải chứa cả hai tenant ở hành vi hiện tại"
    assert len(tenants) > 1, (
        "Nếu khẳng định này đỏ thì gói publish đã trở thành gói theo workspace. "
        "Sửa docstring đầu tệp và sửa câu 'operating per workspace' trong quyển."
    )


def test_thu_pham_vi_theo_tenant_thi_goi_chi_con_tenant_do(hai_tenant):
    """(3) Đường đi tới gói-theo-workspace có sẵn hay không.

    Cùng một hàm thu thập, chạy dưới `tenant_scope(a)` thay vì phạm vi hệ thống.
    Nếu RLS thu hẹp kết quả thì việc đóng gói theo workspace **không cần cơ chế
    mới** — chỉ cần người gọi đặt phạm vi trước khi thu thập.

    Đây là khẳng định có giá trị nhất trong tệp cho phần Hướng phát triển: nó
    biến "chưa làm" thành "một lời gọi nữa là xong", và nó nói được điều đó bằng
    một phép đo chứ bằng một lời hứa.
    """
    from app.tenant_context import tenant_scope

    a, b = hai_tenant
    ua = _make_class(a, f"chi-a-{uuid.uuid4().hex[:6]}")
    ub = _make_class(b, f"chi-b-{uuid.uuid4().hex[:6]}")

    with tenant_scope(a):
        tenants = {r["tenant_id"] for r in _rows(_gather(), "labels.csv")}
        uids = {r["class_uid"] for r in _rows(_gather(), "labels.csv")}

    assert tenants == {a}, (
        "Thu phạm vi theo tenant mà gói vẫn chứa tenant khác: RLS không chạm tới "
        "đường publish, nên gói-theo-workspace cần cơ chế mới chứ không chỉ cần "
        "một lời gọi thu phạm vi."
    )
    assert ua in uids
    assert ub not in uids
