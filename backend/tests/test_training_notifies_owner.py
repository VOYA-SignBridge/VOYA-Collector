"""Cái chuông phải sáng khi một lượt huấn luyện kết thúc.

Vì sao tệp này tồn tại
-----------------------
Ngày 16/08/2026, một lượt rà cả backend cho ra đúng MỘT chỗ gọi
`notifications.notify()`: `app/support.py`. Bảy loại thông báo được khai trong
`notifications.KINDS` — gói dịch vụ, pháp lý, bảo mật, huấn luyện, hỗ trợ, dữ
liệu, hệ thống — và sáu trong số đó không có ai phát. Trên cơ sở dữ liệu sản
xuất: 2 dòng `notifications`, cả hai `kind='support'`.

Người dùng mở trung tâm thông báo ra và thấy trống, kết luận rằng tính năng
hỏng. Nó không hỏng — nó chưa được nối vào gì cả. Đó là một khoảng cách mà
không con số nào trong bộ test cũ đo được, vì không có test nào hỏi "sự kiện X
có sinh ra thông báo không".

Nên tệp này neo đúng một câu hỏi đó cho vòng đời huấn luyện — sự kiện chạy lâu
nhất trong hệ, và vì thế là sự kiện mà người dùng ít có mặt để tự thấy nhất.
"""

from __future__ import annotations

import uuid

import pytest

from app import notifications, training_tasks
from app.storage.metadata_db import _execute
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import system_scope, tenant_scope


def _make_account(prefix: str) -> dict:
    from app.auth import create_user

    name = f"{prefix}{uuid.uuid4().hex[:8]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery")
    return {"id": str(user["id"]), "username": name}


@pytest.fixture
def account():
    acc = _make_account("trnotify")
    yield acc
    from conftest import purge_registered_account

    with system_scope("test cleanup: thong bao huan luyen"):
        _execute("DELETE FROM notifications WHERE user_id = %s", (acc["id"],))
    purge_registered_account(acc["username"])


@pytest.fixture
def scope():
    with tenant_scope(DEFAULT_TENANT_ID):
        yield


def _row(account: dict, status: str = "running") -> dict:
    """Hàng job tối thiểu mà `_update_job` cần.

    KHÔNG ghi xuống cơ sở dữ liệu: bài này đo cái chuông, không đo lớp lưu trữ.
    `_update_job` nuốt lỗi ghi đúng theo thiết kế ("một trục trặc CSDL không
    được giết một lượt huấn luyện"), nên một hàng chưa tồn tại vẫn đi hết đường
    và vẫn tới nhánh thông báo — đó chính là nhánh cần đo.
    """
    return {
        "job_id": str(uuid.uuid4()),
        "status": status,
        "auth_user_id": account["id"],
        "tenant_id": str(DEFAULT_TENANT_ID),
    }


class TestKetThucThiBao:
    @pytest.mark.parametrize(
        "status,severity",
        [("completed", "success"), ("failed", "critical"), ("cancelled", "info")],
    )
    def test_moi_trang_thai_cuoi_deu_sinh_mot_thong_bao(
        self, account, scope, status, severity
    ):
        training_tasks._update_job(_row(account), status=status)

        items = notifications.list_for_user(account["id"])
        assert len(items) == 1, f"trang thai {status} khong sinh thong bao nao"
        assert items[0]["kind"] == "training"
        assert items[0]["severity"] == severity
        # Đường dẫn là thứ biến thông báo thành hành động. Thiếu nó thì người
        # dùng đọc xong vẫn phải tự đi tìm job vừa được nhắc tới.
        assert items[0]["link"] and items[0]["link"].startswith("/training")

    def test_dang_chay_thi_KHONG_bao(self, account, scope):
        """`running` và `queued` không phải tin — chúng là tiếng ồn.

        Cái chuông đắt giá vì nó hiếm khi kêu. Báo mỗi bước chuyển trạng thái là
        cách nhanh nhất để người dùng học cách phớt lờ nó.
        """
        training_tasks._update_job(_row(account, "queued"), status="running")
        assert notifications.list_for_user(account["id"]) == []

    def test_ghi_lai_cung_trang_thai_KHONG_bao_lan_hai(self, account, scope):
        """`_update_job` được gọi nhiều lần trên cùng một hàng trong một lượt
        chạy. Nếu chỉ xét trạng thái MỚI mà không so với trạng thái cũ, một job
        hỏng sẽ báo lại mỗi lần có ai chạm vào hàng của nó."""
        row = _row(account)
        training_tasks._update_job(row, status="completed")
        training_tasks._update_job(row, status="completed", test_acc=0.9)
        assert len(notifications.list_for_user(account["id"])) == 1

    def test_thieu_tenant_thi_khong_ghi_bua(self, account, scope):
        """Fail-closed. Một thông báo gắn sai tenant là một dòng mà RLS sẽ giấu
        khỏi chính người cần đọc — hoặc tệ hơn, hiện cho người khác."""
        row = _row(account)
        row["tenant_id"] = ""
        training_tasks._update_job(row, status="failed")
        assert notifications.list_for_user(account["id"]) == []

    def test_do_chinh_xac_di_vao_than_thong_bao(self, account, scope):
        """Tiêu đề nói việc đã xong; thân nói kết quả. Không có con số thì người
        dùng vẫn phải mở trang huấn luyện ra mới biết lượt chạy đáng hay không."""
        training_tasks._update_job(_row(account), status="completed", test_acc=0.9123)
        body = notifications.list_for_user(account["id"])[0]["body"]
        assert "91.2" in body
