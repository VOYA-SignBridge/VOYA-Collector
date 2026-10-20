"""`tenants` là bảng GỐC, và tới 15/08/2026 nó không hề có RLS.

Đo được trước khi vá, với `voya_test_app` — vai đặc quyền tối thiểu — và
**không** cần đặt sentinel nào:

    SELECT ... FROM tenants   ->  28 dòng
    UPDATE tenants SET ...    ->  UPDATE 28

Cột lộ ra gồm `plan_code`, `billing_status`, `billing_exempt`, `owner_user_id`,
`suspended_at`. Nghĩa là vai ứng dụng liệt kê được mọi tenant của nền tảng và
đổi được gói cước, trạng thái thanh toán hay cờ miễn trừ của bất kỳ tenant nào.

Bảng ấy không bị loại trừ có lý do — nó chưa từng có mặt trong `RLS_TABLES`.

Phạm vi của điều được chứng minh ở đây
======================================
Đây là **Mức I** theo `docs/TENANT_ISOLATION_AND_AUTHZ.md` §4.3: backend đã xác
thực người dùng và tư cách thành viên, rồi mã tin cậy đặt `app.tenant_id`; từ
đó RLS cưỡng chế phạm vi hàng một cách độc lập. Nó chặn truy vấn quên lọc
tenant, chặn truy cập tài nguyên của tenant khác, và hỏng-thì-đóng khi thiếu
ngữ cảnh.

Nó **KHÔNG** chứng minh Mức II. `voya_app` tự đặt được cả `app.tenant_id` lẫn
`app.system_scope`, nên một vai ứng dụng BỊ CHIẾM vẫn tự nhận là tenant khác
được. Đó là giới hạn TCB đã ghi ở §4.1 và cố ý nằm ngoài phạm vi lượt này —
đừng đọc các ca dưới đây thành lời hứa lớn hơn thế.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def hai_tenant():
    """Hai tenant thật, dọn sạch sau. Tên có tiền tố để không lẫn dữ liệu khác."""
    from app.storage.metadata_db import _execute
    from app.tenant_context import system_scope

    # Chữ thường, khớp `_TENANT_ID_RE = \A[a-z0-9][a-z0-9_-]{0,62}\Z`.
    # `normalize_tenant_id` TỪ CHỐI id sai dạng thay vì sửa ngầm, đúng thiết kế
    # — một lỗi gõ không được lặng lẽ trở thành một phân vùng tenant mới.
    a = f"iso-a-{uuid.uuid4().hex[:8]}"
    b = f"iso-b-{uuid.uuid4().hex[:8]}"
    with system_scope("test: dựng hai tenant cho phép kiểm cách ly"):
        for t in (a, b):
            _execute(
                "INSERT INTO tenants(tenant_id, display_name, slug, is_active) "
                "VALUES(%s, %s, %s, TRUE)", (t, f"iso {t}", t.lower()))
    yield a, b
    with system_scope("test cleanup"):
        _execute("DELETE FROM tenants WHERE tenant_id = ANY(%s)", ([a, b],))


def _doc(sql, params=None):
    from app.storage.metadata_db import _fetch_all

    return _fetch_all(sql, params or ())


@pytest.mark.integration
class TestDocTrongPhamViTenant:
    def test_khong_co_ngu_canh_thi_KHONG_THAY_GI(self, hai_tenant):
        """Hỏng-thì-đóng. Thiếu ngữ cảnh phải là 0 dòng, không phải mọi dòng."""
        from app.tenant_context import no_scope

        with no_scope():
            assert _doc("SELECT tenant_id FROM tenants") == []

    def test_truy_van_QUEN_loc_tenant_van_chi_thay_minh(self, hai_tenant):
        """Đây là điều RLS thực sự mua được ở Mức I.

        Câu SQL dưới đây KHÔNG có `WHERE tenant_id` — đúng kiểu lỗi đã gây ba
        sự cố fail-open ở mặt phẳng danh tính. RLS phải bù vào chỗ đó.
        """
        from app.tenant_context import tenant_scope

        a, b = hai_tenant
        with tenant_scope(a):
            thay = {r["tenant_id"] for r in _doc("SELECT tenant_id FROM tenants")}

        assert thay == {a}, f"thay ca tenant khac: {sorted(thay - {a})[:5]}"

    def test_hoi_DICH_DANH_tenant_khac_van_KHONG_thay(self, hai_tenant):
        """Đoán id của tenant khác không mở được gì."""
        from app.tenant_context import tenant_scope

        a, b = hai_tenant
        with tenant_scope(a):
            assert _doc("SELECT tenant_id FROM tenants WHERE tenant_id = %s", (b,)) == []


@pytest.mark.integration
class TestGhiTrongPhamViTenant:
    """USING chi phối dòng ĐANG CÓ; WITH CHECK chi phối dòng SAU khi ghi.

    Hai vế phải cùng đóng, và mỗi ca dưới đây nhắm đúng một vế — nếu không thì
    một bản vá chỉ đúng nửa vẫn xanh.
    """

    def _cua_b(self, b):
        from app.tenant_context import system_scope

        with system_scope("test: đọc lại bằng phạm vi nền tảng"):
            r = _doc("SELECT display_name, tenant_id FROM tenants WHERE tenant_id = %s", (b,))
        return r[0] if r else None

    def test_UPDATE_tenant_khac_khong_cham_duoc_dong_nao(self, hai_tenant):
        from app.storage.metadata_db import _execute
        from app.tenant_context import tenant_scope

        a, b = hai_tenant
        truoc = self._cua_b(b)

        with tenant_scope(a):
            _execute("UPDATE tenants SET display_name = 'BI CHIEM' WHERE tenant_id = %s", (b,))

        assert self._cua_b(b)["display_name"] == truoc["display_name"], (
            "tenant A sua duoc ban ghi cua tenant B")

    def test_DELETE_tenant_khac_khong_cham_duoc_dong_nao(self, hai_tenant):
        from app.storage.metadata_db import _execute
        from app.tenant_context import tenant_scope

        a, b = hai_tenant
        with tenant_scope(a):
            _execute("DELETE FROM tenants WHERE tenant_id = %s", (b,))

        assert self._cua_b(b) is not None, "tenant A xoa duoc tenant B"

    def test_INSERT_mao_danh_tenant_khac_bi_TU_CHOI(self, hai_tenant):
        """Vế WITH CHECK. Thiếu nó thì A tạo được dòng mang nhãn B."""
        from app.storage.metadata_db import _execute
        from app.tenant_context import tenant_scope

        a, _ = hai_tenant
        gia = f"ISO-FAKE-{uuid.uuid4().hex[:8]}"
        with tenant_scope(a):
            with pytest.raises(Exception) as loi:
                _execute(
                    "INSERT INTO tenants(tenant_id, display_name, slug, is_active) "
                    "VALUES(%s, %s, %s, TRUE)", (gia, "mao danh", gia.lower()))

        assert "row-level security" in str(loi.value).lower(), str(loi.value)[:200]

    def test_doi_DANH_TINH_tenant_cua_chinh_minh_bi_TU_CHOI(self, hai_tenant):
        """A không đổi được `tenant_id` của chính nó sang một giá trị khác.

        Ca này ĐƯỢC bảo vệ, nhưng KHÔNG phải bởi `WITH CHECK` — và chỗ đó đáng
        ghi lại, vì bản đầu của tệp này tuyên bố sai.

        Đo ngày 15/08/2026 dưới đột biến `WITH CHECK (true)` (đã xác nhận có
        hiệu lực: `pg_policies.with_check = 'true'`):

            sqlstate   42501
            msg        new row violates row-level security policy
                       for table "tenants"
            constraint None      <- không phải PK
            table      None      <- không phải FK

        Đúng như vậy với CẢ hai trường hợp: đích đã tồn tại, và đích chưa tồn
        tại. Nên hai giả thuyết đầu tiên — khoá chính trùng, và khoá ngoại lan
        xuống bảng con — đều bị loại (33 khoá ngoại trỏ vào `tenants` đều là
        `ON UPDATE RESTRICT`, không CASCADE).

        Cơ chế thật thì CHƯA xác định, và tệp này cố ý không đoán một cơ chế.
        Điều được chứng minh, và chỉ điều này: phép ghi bị RLS trên `tenants`
        từ chối, kể cả khi vế `WITH CHECK` đã bị vô hiệu hoá.

        Bằng chứng cho `WITH CHECK` nằm ở ca INSERT bên trên — ca đó ĐỎ dưới
        cùng đột biến.

        Một lưu ý về cách gọi tên: với `tenants`, `tenant_id` LÀ danh tính của
        chính hàng đó, nên đây gần với "đổi danh tính tenant" hơn là "chuyển
        một tài nguyên từ A sang B".
        """
        from app.storage.metadata_db import _execute
        from app.tenant_context import tenant_scope

        a, b = hai_tenant
        with tenant_scope(a):
            with pytest.raises(Exception) as loi:
                _execute("UPDATE tenants SET tenant_id = %s WHERE tenant_id = %s", (b, a))

        assert "row-level security" in str(loi.value).lower(), str(loi.value)[:200]


@pytest.mark.integration
class TestDuongDieuKhien_VanChayDuoc:
    """Bật RLS mà làm chết đường điều khiển thì là đổi lỗi này lấy lỗi khác."""

    def test_pham_vi_nen_tang_van_liet_ke_duoc_moi_tenant(self, hai_tenant):
        from app.tenant_context import system_scope

        a, b = hai_tenant
        with system_scope("test: đường điều khiển liệt kê mọi tenant"):
            thay = {r["tenant_id"] for r in _doc("SELECT tenant_id FROM tenants")}

        assert {a, b} <= thay

    def test_kiem_tenant_DICH_ton_tai_van_dung(self, hai_tenant):
        """Ca canh cho `routers/vocabulary.py`.

        Nó hỏi "tenant ĐÍCH có tồn tại không" về một tenant KHÁC. Trước lượt
        này nó không nằm trong phạm vi nào; sau khi bật RLS mà không bọc, nó sẽ
        trả 0 dòng và endpoint kết luận "Tenant không tồn tại" — một cái 404
        nghe hợp lý cho một tenant vẫn đang ở đó.
        """
        from app.tenant_context import system_scope, tenant_scope

        a, b = hai_tenant
        with tenant_scope(a):
            with system_scope("vocabulary: kiểm tenant ĐÍCH tồn tại trước khi sao chép"):
                co = _doc("SELECT 1 FROM tenants WHERE tenant_id = %s "
                          "AND deleted_at IS NULL", (b,))

        assert co, "duong dieu khien khong con thay tenant dich"
