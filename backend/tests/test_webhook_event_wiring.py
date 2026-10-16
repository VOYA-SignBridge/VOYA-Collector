"""Mọi loại sự kiện đã khai báo phải có chỗ thật sự phát nó.

Đây là loại khoảng trống không có gì đỏ: `EVENT_TYPES` liệt kê sáu sự kiện,
giao diện dựng ô chọn từ danh sách đó, khách hàng đăng ký nhận
`training.completed` — và không dòng mã nào gọi `emit` với tên đó. Không lỗi,
không cảnh báo, không test nào đỏ. Khách hàng chỉ đơn giản chờ mãi.

Đã xảy ra thật trong chính đợt này: v4 khai báo sáu sự kiện và nối đúng MỘT.

Cách kiểm là quét AST của cây `app/` tìm mọi lời gọi `emit(...)` có đối số thứ
hai là hằng chuỗi. Quét AST chứ không grep vì grep bắt cả tên sự kiện nằm
trong docstring, trong chú thích, trong chính `EVENT_TYPES` — đúng cái bẫy đã
làm một test an ninh khác xanh giả vào 2026-08-08.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.webhooks import EVENT_TYPES

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _event_names_used_at_call_sites() -> set[str]:
    """Tên sự kiện xuất hiện làm ĐỐI SỐ của một lời gọi, ở bất kỳ đâu trong `app/`.

    Khớp theo GIÁ TRỊ, không theo tên hàm — và đó là bản sửa của một bộ dò sai
    tôi viết trước đó. Bản đầu tìm riêng những lời gọi tên `emit`, nên nó bỏ
    sót hai sự kiện huấn luyện: chúng đi qua hàm bọc `_emit_training_event`,
    vốn tồn tại vì tenant phải lấy từ hàng job chứ không từ ngữ cảnh. Bộ dò
    khi đó báo "chưa nối" cho mã đã nối đúng.

    Đổi sang khớp giá trị cũng làm bộ dò không còn phụ thuộc vào việc người
    viết đặt tên hàm bọc thế nào — một ràng buộc mà không ai biết là mình đang
    phải tuân theo.

    Giới hạn được nhận: nó chứng minh tên sự kiện **được dùng như dữ liệu ở một
    chỗ gọi**, không chứng minh chỗ gọi đó thực sự chạy tới `emit`. Một khẳng
    định mạnh hơn cần phân tích luồng gọi. Thứ nó bắt là điều đã thực sự xảy
    ra: một tên nằm trong danh sách mà không mã nào chạm tới.

    Bỏ qua `app/webhooks.py` — nó ĐỊNH NGHĨA danh sách, nên tính vào là khiến
    mọi sự kiện luôn "đã được nối".
    """
    declared = set(EVENT_TYPES)
    found: set[str] = set()
    for path in APP_ROOT.rglob("*.py"):
        if path.name == "webhooks.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - chỉ xảy ra khi mã đang hỏng
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for argument in node.args:
                if (
                    isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                    and argument.value in declared
                ):
                    found.add(argument.value)
    return found


@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_declaredEventType_hasAtLeastOneCallSite(event_type: str):
    """Từng sự kiện một, không gộp thành một khẳng định.

    Tham số hoá để báo cáo nói thẳng sự kiện NÀO chưa được nối, thay vì một
    dòng "tập hợp không khớp" bắt người đọc tự so hai danh sách.
    """
    assert event_type in _event_names_used_at_call_sites(), (
        f"{event_type!r} có trong EVENT_TYPES nhưng không dòng mã nào phát nó. "
        f"Khách hàng đăng ký nhận nó sẽ chờ mãi mà không có gì đỏ ở đâu cả."
    )


def test_emitCallSite_neverUsesAnUndeclaredName():
    """Chiều ngược lại: một lời gọi `emit` với tên không có trong danh sách.

    `emit` từ chối tên lạ lúc CHẠY và chỉ ghi một dòng log, nên một lỗi gõ sai
    ở chỗ gọi biến thành sự im lặng hoàn toàn. Bắt nó ở đây, lúc còn đọc được
    mã, thay vì lúc có người hỏi vì sao webhook không tới.

    Chỗ này khớp theo TÊN HÀM (`emit` và đối số thứ hai là chuỗi) chứ không
    theo giá trị — ngược với hàm quét bên trên, và bắt buộc phải thế: ta đang
    đi tìm những giá trị KHÔNG nằm trong danh sách, nên không thể lọc theo
    danh sách.
    """
    undeclared: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        if path.name == "webhooks.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or len(node.args) < 2:
                continue
            name = (
                node.func.id if isinstance(node.func, ast.Name)
                else node.func.attr if isinstance(node.func, ast.Attribute)
                else None
            )
            if name != "emit":
                continue
            second = node.args[1]
            if (
                isinstance(second, ast.Constant)
                and isinstance(second.value, str)
                and second.value not in EVENT_TYPES
            ):
                undeclared.append(f"{path.name}: {second.value!r}")

    assert not undeclared, (
        f"những tên này được phát nhưng không có trong EVENT_TYPES: {undeclared}"
    )
