"""Mọi bảng mang `tenant_id` phải có RLS — hoặc phải là ngoại lệ ĐÃ ĐƯỢC SOI.

    TẤT CẢ bảng có cột tenant_id
        =  ĐƯỢC RLS BẢO VỆ
        ∪  NGOẠI LỆ ĐÃ RÀ SOÁT TƯỜNG MINH

Vì sao tệp này tồn tại
======================
Ngày 15/08/2026, trong lúc đọc mã 31 chỗ gọi `system_scope` của nhóm A, phát
hiện `tenants` — bảng liệt kê MỌI tenant của nền tảng — đang TẮT hoàn toàn RLS.
Nó không bị loại có chủ ý: nó chưa từng có mặt trong danh sách bảng của
`app/storage/rls.py`.

Đo được với `voya_test_app`, vai đặc quyền tối thiểu, KHÔNG cần đặt sentinel:

    SELECT ... FROM tenants   ->  28 dòng
    UPDATE tenants SET ...    ->  UPDATE 28

Cột lộ ra gồm `plan_code`, `billing_status`, `billing_exempt`, `owner_user_id`,
`suspended_at`.

Khác với lỗ `app.system_scope` (vai ứng dụng tự lật được cờ), lỗ này KHÔNG cần
mẹo gì: bất kỳ truy vấn `tenants` nào thiếu điều kiện lọc đều trả về toàn bộ.

Bài kiểm này KHÔNG vá lỗ
========================
Nó chốt lại để lỗ không LỚN THÊM. Thêm một bảng mang `tenant_id` mà quên khai
báo trong `rls.py` sẽ làm ca này đỏ ngay, thay vì được phát hiện vài tháng sau
bởi một lượt đọc mã tình cờ — đúng cách hai bảng dưới đây đã lọt.

Danh sách ngoại lệ chỉ được RÚT NGẮN
====================================
Thêm tên vào đây là một quyết định phải nêu lý do, và lý do phải là "đã soi và
kết luận được", không phải "đang vướng". Cả hai mục hiện tại đều là KHIẾM
KHUYẾT ĐANG MỞ, không phải thiết kế.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#: Bảng có `tenant_id` mà KHÔNG bật RLS phải được bảo vệ bằng cách KIA — ranh
#: giới quyền ở tầng vai. Danh sách này KHÔNG phải chỗ khai báo: nguồn sự thật
#: là `app/storage/control_plane.py`, và nhập từ đó chứ không chép sang đây.
#:
#: Vì sao hai kiểu bảo vệ chứ không phải một
#: -----------------------------------------
#: `tenant_purges` là sổ cái nền tảng, và `tenant_lifecycle` xoá dòng `tenants`
#: TRƯỚC khi ghi sổ — nên lúc dòng sổ ra đời, tenant ấy đã không còn tồn tại.
#: Một chính sách "chỉ thấy dòng của tenant mình" không có gì để so, và bật RLS
#: rồi lại mở `system_scope` để vượt qua nó chỉ làm con số phủ đẹp lên mà không
#: thêm chút bảo vệ nào.
#:
#: Nên bảng ấy được bảo vệ bằng thứ đúng với bản chất mối đe doạ: vai ứng dụng
#: KHÔNG có quyền nào trên nó, và một danh tính khác có đúng quyền tối thiểu.
#:
#: Danh sách ngoại lệ KHÔNG có giải trình giờ là rỗng.
from app.storage.control_plane import (  # noqa: E402
    APP_TABLE_PRIVILEGES,
    CONTROL_PLANE_TABLES,
    TEST_CONTROL_ROLE,
)

#: Vai ỨNG DỤNG mà bộ test chạy dưới đó. Không được có quyền nào trên bảng điều
#: khiển. `voya_app` (vai sản xuất) cũng bị canh, vì nó tồn tại trên cụm này.
VAI_UNG_DUNG = ("voya_test_app", "voya_app")

#: Không còn ngoại lệ nào thiếu giải trình. Giữ tên biến để phần còn lại của
#: tệp đọc được, nhưng nó phải ở lại RỖNG.
NGOAI_LE_DANG_MO: frozenset[str] = frozenset()

SQL_BANG_CO_TENANT_ID = """
SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = current_schema()
  AND c.relkind = 'r'
  AND EXISTS (
      SELECT 1 FROM pg_attribute a
      WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped
  )
ORDER BY c.relname
"""


def _bang() -> list[tuple[str, bool, bool]]:
    from app.storage.metadata_db import _migration_cursor

    with _migration_cursor() as cur:
        cur.execute(SQL_BANG_CO_TENANT_ID)
        return [(r[0], r[1], r[2]) for r in cur.fetchall()]


def _quyen(cur, bang: str, vai: str) -> set[str]:
    """Quyền THỰC TẾ của một vai trên một bảng, hỏi cơ sở dữ liệu.

    `has_table_privilege` chứ không `information_schema`: nó tính cả quyền thừa
    hưởng qua tư cách thành viên vai, nên một đường leo thang kiểu "cấp cho vai
    cha" cũng bị bắt.
    """
    ra = set()
    for q in APP_TABLE_PRIVILEGES:
        cur.execute("SELECT has_table_privilege(%s, %s, %s)", (vai, bang, q))
        if cur.fetchone()[0]:
            ra.add(q)
    return ra


@pytest.mark.integration
class TestPhuRLS:
    def test_moi_bang_tenant_deu_duoc_phan_loai(self):
        """Ca chính. Một bảng tenant mới mà quên phân loại sẽ đỏ ngay tại đây.

        Hai lối hợp lệ, và chỉ hai:

            RLS      -> khai báo ở `app/storage/rls.py`
            ĐIỀU KHIỂN -> khai báo ở `app/storage/control_plane.py`

        Không có lối thứ ba, và không còn danh sách "ngoại lệ đang mở".
        """
        thieu = sorted(t for t, rls, _ in _bang() if not rls)
        chua_phan_loai = [t for t in thieu if t not in CONTROL_PLANE_TABLES]

        assert not chua_phan_loai, (
            f"bang mang tenant_id nhung TAT RLS va KHONG duoc khai bao la bang "
            f"dieu khien: {chua_phan_loai}.\n"
            f"Them vao app/storage/rls.py, hoac — neu that su la du lieu mat "
            f"phang dieu khien — them vao CONTROL_PLANE_TABLES kem tap quyen "
            f"toi thieu, va tra loi duoc bon cau hoi o dau tep control_plane.py.")

    def test_khong_con_ngoai_le_thieu_giai_trinh(self):
        """Danh sách ngoại lệ phải ở lại RỖNG.

        Trước 15/08/2026 `tenant_purges` nằm ở đây với ghi chú "nhiều khả năng
        `voya_app` không nên có quyền ghi trực tiếp chút nào". Nó đã được phân
        loại thật; danh sách này không được sống lại như một lối thoát.
        """
        assert not NGOAI_LE_DANG_MO, (
            f"danh sach ngoai le thieu giai trinh da song lai: "
            f"{sorted(NGOAI_LE_DANG_MO)}")

    def test_bang_dieu_khien_khong_duoc_bat_RLS_ma_van_o_trong_danh_sach(self):
        """Một bảng không được vừa là bảng RLS vừa là bảng điều khiển.

        Nếu ai đó bật RLS cho một bảng điều khiển, phân loại đã đổi và khai báo
        phải đi theo — nếu không, `test_moi_bang_tenant_deu_duoc_phan_loai` sẽ
        xanh nhờ nhánh sai và không ai kiểm tập quyền nữa.
        """
        co_rls = {t for t, rls, _ in _bang() if rls}
        lan = co_rls & set(CONTROL_PLANE_TABLES)

        assert not lan, (
            f"{sorted(lan)} vua bat RLS vua duoc khai bao la bang dieu khien. "
            f"Chon MOT: neu no that su la du lieu tenant thi go khoi "
            f"CONTROL_PLANE_TABLES; neu la du lieu dieu khien thi dung bat RLS "
            f"roi lai mo system_scope de vuot qua chinh no.")

    def test_vai_ung_dung_khong_cham_duoc_bang_dieu_khien(self):
        """Nửa THẬT của bảo vệ nhóm B. Không có ca này thì khai báo chỉ là chữ.

        Đây là chỗ dễ gian lận nhất: thêm tên vào `CONTROL_PLANE_TABLES` là làm
        ca phân loại xanh ngay, mà chẳng REVOKE gì cả. Ca này hỏi cơ sở dữ liệu.
        """
        from app.storage.metadata_db import _migration_cursor

        vi_pham = {}
        with _migration_cursor() as cur:
            for bang in CONTROL_PLANE_TABLES:
                for vai in VAI_UNG_DUNG:
                    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (vai,))
                    if cur.fetchone() is None:
                        continue  # vai không tồn tại trên cụm này
                    co = _quyen(cur, bang, vai)
                    if co:
                        vi_pham[f"{vai}.{bang}"] = sorted(co)

        assert not vi_pham, (
            f"vai ung dung VAN co quyen truc tiep tren bang dieu khien: "
            f"{vi_pham}. Chay lai `bash scripts/provision_test_db_roles.sh` "
            f"(test) hoac `python -m app.cli.provision_db_roles` (san xuat).")

    def test_vai_dieu_khien_co_DUNG_tap_quyen_da_khai_bao(self):
        """Chính xác theo CẢ HAI chiều — thiếu thì đường ghi hỏng, thừa thì đỏ.

        Chiều "thừa" mới là chiều đáng giá: cấp thêm `DELETE` cho tiện sẽ bị bắt
        ở đây, chứ không nằm im tới ngày có người dùng tới nó.
        """
        from app.storage.metadata_db import _migration_cursor

        lech = {}
        with _migration_cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s",
                        (TEST_CONTROL_ROLE,))
            if cur.fetchone() is None:
                pytest.skip(f"{TEST_CONTROL_ROLE} chua duoc cap phat tren cum nay")
            for bang, mong_doi in CONTROL_PLANE_TABLES.items():
                co = _quyen(cur, bang, TEST_CONTROL_ROLE)
                if co != set(mong_doi):
                    lech[bang] = {"co": sorted(co), "khai_bao": sorted(mong_doi)}

        assert not lech, (
            f"quyen thuc te cua {TEST_CONTROL_ROLE} lech khoi khai bao: {lech}")

    def test_bang_da_bao_ve_deu_dung_FORCE(self):
        """`ENABLE` không thôi là chưa đủ: chủ sở hữu bảng vẫn được miễn.

        Chủ sở hữu chính là vai migration, nên thiếu `FORCE` thì mọi script bảo
        trì nối bằng DSN ấy sẽ lặng lẽ thấy mọi tenant.
        """
        khong_force = sorted(t for t, rls, force in _bang() if rls and not force)

        assert not khong_force, (
            f"bat RLS nhung thieu FORCE: {khong_force} — chu so huu bang van "
            f"duoc mien chinh sach")
