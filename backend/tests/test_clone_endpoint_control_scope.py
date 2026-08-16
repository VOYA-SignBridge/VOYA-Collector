"""`POST /vocabulary/catalog/clone` — đường ĐIỀU KHIỂN nhìn được tenant ĐÍCH.

Vì sao tệp này tồn tại
======================
Ngày 15/08/2026 `tenants` được bật RLS + FORCE. Trước đó phép kiểm "tenant đích
có tồn tại không" ở `routers/vocabulary.py` **không nằm trong phạm vi nào** —
nó chạy dưới ngữ cảnh tenant của người gọi, hỏi về một tenant KHÁC.

Sau khi bật RLS mà không bọc, câu ấy trả 0 dòng và endpoint kết luận:

    404  "Tenant '<id>' không tồn tại."

cho một tenant vẫn đang ở đó. Sai theo đúng kiểu tệ nhất: thông báo nghe hợp
lý, người dùng tin là họ gõ nhầm id, và không có gì trong nhật ký nói ngược lại.

Vì sao KHÔNG kiểm bằng khuôn mẫu
================================
Bản đầu của phép kiểm này khẳng định *khuôn* `system_scope(...)` hoạt động —
tức là dựng lại đúng đoạn mã ấy trong bài kiểm rồi kiểm nó. Khuôn thì đúng,
nhưng nó KHÔNG chứng minh `routers/vocabulary.py` đang dùng khuôn ấy: gỡ
`system_scope` khỏi đúng chỗ đó thì bài kiểm kia vẫn xanh.

Nên tệp này gọi qua ĐÚNG endpoint thật.

Ba điều được khoá
=================
1. Người gọi CÓ quyền + tenant đích tồn tại  -> KHÔNG được 404 "không tồn tại",
   và phải đạt kết quả nghiệp vụ cụ thể (không chỉ "khác 404" — 500 cũng khác
   404).
2. Người gọi KHÔNG quyền + cùng tenant đích  -> vẫn bị TỪ CHỐI.
3. Đột biến gỡ `system_scope` tại `routers/vocabulary.py` -> ca (1) ĐỎ.

Điểm (2) là điểm dễ mất nhất: `system_scope` ở đây chỉ chứng minh **khả năng
nhìn thấy** tenant đích để thực hiện một thao tác điều khiển ĐÃ được cho phép.
Nó không phải cơ chế phân quyền, và không được biến một người gọi không có
quyền thành hợp lệ.

`AUTHZ_MODE` hiện là `shadow`, nên phía âm kiểm đúng đường quyết định ĐANG
cưỡng chế (`assert_system_admin` của chính mặt phẳng này), không giả định
Casbin đã là bên cưỡng chế.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DUONG_DAN = "/vocabulary/catalog/clone"


@pytest.fixture
def tenant_dich():
    """Một tenant ĐÍCH có thật, và dọn sạch mọi thứ lượt sao chép sinh ra."""
    from app.storage.metadata_db import _execute
    from app.tenant_context import system_scope

    tid = f"clone-target-{uuid.uuid4().hex[:8]}"
    with system_scope("test: dựng tenant đích"):
        _execute(
            "INSERT INTO tenants(tenant_id, display_name, slug, is_active) "
            "VALUES(%s, %s, %s, TRUE)", (tid, f"clone {tid}", tid))
    yield tid

    # Dọn theo THỨ TỰ KHOÁ NGOẠI, và không được bỏ dở giữa chừng.
    #
    # 33 khoá ngoại trỏ vào `tenants` đều là RESTRICT, nên bỏ sót một bảng con
    # là không xoá được tenant. Bản đầu của fixture này nhớ ba bảng và quên
    # `registry_versions` (do `_bump()` ghi) — lỗi hiện ra ở TEARDOWN nên nó
    # không chỉ vào nguyên nhân, và tenant rác ở lại cơ sở dữ liệu test.
    #
    # Hậu quả không dừng ở tệp này: lượt full suite kế tiếp có
    # `test_every_live_tenant_has_exactly_one_open_subscription` ĐỎ, vì tenant
    # rác ấy không có đăng ký nào. Một fixture dọn dở làm đỏ một bài kiểm ở tệp
    # khác, về một bất biến chẳng liên quan.
    #
    # `finally` từng bảng: một lần xoá hỏng không được ngăn các lần sau chạy.
    with system_scope("test cleanup"):
        for bang in ("registry_versions", "dialects", "recognition_profiles",
                     "vocabulary_registry_meta", "tenant_subscriptions"):
            try:
                _execute(f"DELETE FROM {bang} WHERE tenant_id = %s", (tid,))
            except Exception:  # noqa: BLE001 — dọn dẹp, không được che ca chính
                pass
        _execute("DELETE FROM tenants WHERE tenant_id = %s", (tid,))


def _client(*, la_admin: bool):
    from app.auth import require_admin
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: {
        "id": None, "username": "quan-tri" if la_admin else "nguoi-thue",
        "is_admin": la_admin,
    }
    return app, TestClient(app)


@pytest.fixture
def client_admin():
    from app.auth import require_admin

    app, c = _client(la_admin=True)
    yield c
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def client_khong_quyen():
    """Đăng nhập được, nhưng KHÔNG phải quản trị nền tảng.

    `require_admin` được ghi đè để cho request đi qua, nên thứ đang được kiểm
    là hàng rào RIÊNG của mặt phẳng này (`assert_system_admin`), chứ không phải
    dependency đứng trước nó. Hai lớp là cố ý tách rời.
    """
    from app.auth import require_admin

    app, c = _client(la_admin=False)
    yield c
    app.dependency_overrides.pop(require_admin, None)


@pytest.mark.integration
class TestDuongDieuKhienNhinThayTenantDich:
    def test_nguoi_co_quyen_sao_chep_duoc_vao_tenant_dich(self, client_admin, tenant_dich):
        """Ca DƯƠNG, và nó phải khẳng định KẾT QUẢ chứ không phải "khác 404".

        Một cái 500 cũng khác 404. Nếu chỉ kiểm mã trạng thái thì đột biến gỡ
        `system_scope` có thể chuyển 404 thành một lỗi khác mà vẫn xanh.
        """
        r = client_admin.post(DUONG_DAN, json={"tenant_id": tenant_dich})

        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        body = r.json()
        assert body["tenant_id"] == tenant_dich
        # Đã đi QUA bước tra tenant và tới đúng bước nghiệp vụ.
        assert "cloned" in body and isinstance(body["cloned"], dict)
        assert body["cloned"], "khong sao chep duoc muc nao — chua toi buoc nghiep vu"
        assert "registry_version" in body

    def test_nguoi_KHONG_quyen_van_bi_tu_choi(self, client_khong_quyen, tenant_dich):
        """`system_scope` là khả năng NHÌN, không phải phép PHÂN QUYỀN.

        Nếu ca này hỏng thì bản vá đã biến một thao tác điều khiển thành đường
        vượt tenant cho bất kỳ ai đăng nhập được.
        """
        r = client_khong_quyen.post(DUONG_DAN, json={"tenant_id": tenant_dich})

        assert r.status_code == 403, f"{r.status_code}: {r.text[:200]}"

    def test_tenant_dich_KHONG_ton_tai_van_bao_404(self, client_admin):
        """Chốt chặn không được đi quá tay.

        Sau khi bọc `system_scope`, phép kiểm phải vẫn TỪ CHỐI một id gõ sai —
        nếu không thì hàng danh mục sẽ được ghi dưới một tenant không ai với
        tới được, đúng điều chú thích ở endpoint cảnh báo.
        """
        r = client_admin.post(DUONG_DAN, json={"tenant_id": f"khong-co-{uuid.uuid4().hex[:8]}"})

        assert r.status_code == 404
        assert "không tồn tại" in r.json().get("detail", "")
