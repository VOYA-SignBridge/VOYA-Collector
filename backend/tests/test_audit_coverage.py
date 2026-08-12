"""Danh sách hành động PHẢI để lại dấu vết kiểm toán.

Vì sao cần một test kiểu "danh sách" thay vì test từng endpoint
---------------------------------------------------------------
Một hành động thiếu dấu vết không hỏng gì cả. Endpoint chạy đúng, người dùng
thấy đúng kết quả, không có lỗi nào ở đâu. Nó chỉ hỏng vào tháng sau, khi ai đó
hỏi "ai gộp phương ngữ này?" và câu trả lời là không có câu trả lời. Không một
bộ test hành vi nào bắt được loại thiếu sót đó, vì không có hành vi nào sai.

Nên chỗ này giữ một DANH SÁCH tường minh. Thêm một hành động vào danh sách là
một lời hứa; xoá nó khỏi danh sách là một quyết định phải viết ra lý do.

Đây KHÔNG phải danh sách đầy đủ mọi phép ghi trong hệ thống, và cố làm cho nó
đầy đủ sẽ biến nó thành thứ người ta cập nhật cho xong. Tiêu chí vào danh sách
là một câu hỏi: *nếu việc này xảy ra mà không ai nhớ, sáu tháng sau có ai cần
biết ai đã làm không?* Đổi vai một thành viên thì có. Đánh dấu một thông báo là
đã đọc thì không.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"

#: (hành động, tệp router phải chứa nó, vì sao nó đáng ghi)
PHAI_CO_DAU_VET = [
    # --- mặt phẳng an ninh: quản trị viên tác động lên một CON NGƯỜI ---
    ("security.2fa.disabled", "two_factor.py",
     "tắt yếu tố thứ hai là đúng việc người chiếm được mật khẩu sẽ làm đầu tiên"),
    ("security.2fa.recovery_codes_regenerated", "two_factor.py",
     "cấp lại mã khôi phục giết bộ cũ; chủ tài khoản cần biết vì sao mã cũ hỏng"),

    # --- quyền ký SOT: ai được công bố danh mục mà cả hệ thống tin ---
    ("security.sot.machine_registered", "sot_admin.py",
     "cấp quyền ký SOT cho một máy mới"),
    ("security.sot.machine_revoked", "sot_admin.py",
     "thu hồi giữa chừng làm sot-init thoát mã 4 và cả stack không lên"),

    # --- dữ liệu của người khác bị di chuyển, không hoàn tác được ---
    ("vocabulary.dialect.merged", "vocabulary.py",
     "gộp phương ngữ đổi nhãn mọi mẫu người đóng góp đã thu"),
    ("vocabulary.dialect.approved", "vocabulary.py",
     "biến một đề xuất thành mục chính thức của danh mục"),

    # --- quyền trong tổ chức ---
    ("tenant.member_role_changed", "tenants.py",
     "đổi vai là đổi quyền; cột `role` chỉ nói vai HIỆN TẠI"),
    ("tenant.member_removed", "tenants.py",
     "người bị gỡ mất quyền xem chính dữ liệu họ đã đóng góp"),

    # --- những cái đã có từ trước, giữ lại để không ai vô tình gỡ ---
    ("data.class.purge", "classes.py", "xoá vĩnh viễn một nhãn và mẫu bên trong"),
    ("data.sample.purge", "dataset.py", "xoá vĩnh viễn một mẫu"),
    ("legal.publish", "legal_admin.py", "công bố văn bản pháp lý là bằng chứng"),
    ("sudo.elevate", "admin.py", "nâng quyền tạm thời"),
]


@pytest.mark.parametrize("action,tep,ly_do", PHAI_CO_DAU_VET,
                         ids=[a for a, _, _ in PHAI_CO_DAU_VET])
def test_hanh_dong_nay_co_ghi_kiem_toan(action, tep, ly_do):
    """Hành động phải được ghi, bằng MỘT TRONG HAI lối gọi hợp lệ.

    * `audit.record("mien.viec")` — chỉ vào nhật ký bền.
    * `activity.log_security_event("viec")` — vào **cả hai** nhật ký, và tự
      thêm tiền tố `security.`. Đây là lối đúng cho mọi thứ thuộc mặt phẳng an
      ninh: gọi thẳng `audit.record("security.…")` thì sự kiện mang tiền tố an
      ninh nhưng lại VẮNG MẶT ở bảng "Nhật ký bảo mật" — một chỗ lệch mà người
      đọc không có cách nào đoán ra.

    Test nhận cả hai vì thứ nó bảo vệ là **dấu vết có tồn tại không**, không
    phải hàm nào được gọi.
    """
    path = ROUTERS / tep
    assert path.exists(), f"{tep} không còn tồn tại — cập nhật danh sách"
    src = path.read_text(encoding="utf-8")

    truc_tiep = f'"{action}"' in src
    qua_security = (
        action.startswith("security.")
        and f'"{action[len("security."):]}"' in src
        and "log_security_event" in src
    )
    assert truc_tiep or qua_security, (
        f"{tep} không còn ghi kiểm toán cho {action!r}.\n"
        f"Vì sao nó đáng ghi: {ly_do}"
    )


def test_khong_ghi_bi_mat_vao_detail():
    """`detail` của một dòng kiểm toán KHÔNG được mang bí mật.

    `audit._redact` che theo TÊN KHOÁ, nên nó chỉ cứu được khi người viết đặt
    tên khoá trùng danh sách. Một dòng như `detail={"codes": [...]}` lọt qua
    sạch sẽ. Rẻ hơn là đừng đưa vào ngay từ đầu — và đây là chỗ nhắc điều đó
    bằng một phép kiểm chạy được, chứ không bằng một dòng trong tài liệu.
    """
    xau = ("recovery_codes", "private_key", "password", "totp_secret", "token")
    loi = []
    for path in ROUTERS.glob("*.py"):
        src = path.read_text(encoding="utf-8")
        for m in re.finditer(r"audit\.record\((.{0,600}?)\)\n", src, re.S):
            doan = m.group(1)
            if "detail=" not in doan:
                continue
            for tu in xau:
                if f'"{tu}"' in doan:
                    loi.append(f"{path.name}: detail có khoá {tu!r}")
    assert not loi, "\n".join(loi)


def test_moi_hanh_dong_deu_theo_khuon_mien_diem_cham():
    """`mien.doi_tuong.viec` — tiền tố là thứ giao diện lọc theo.

    `AdminActivityPage` lọc nhật ký bằng tiền tố (`security.`, `data.`,
    `tenant.`…). Một hành động đặt tên ngoài khuôn vẫn ghi được, vẫn đọc được
    bằng SQL, và vẫn hiện ra dưới "Tất cả" — nó không biến mất. Nhưng nó không
    LỌC RA được, và ở một bảng chỉ dài thêm theo thời gian thì "không lọc ra
    được" và "không tìm thấy" là cùng một thứ với người đang cần nó.
    """
    # Cho phép chữ số ở đầu một đoạn: `security.2fa.disabled` là tên đúng và
    # dễ đọc, và một khuôn từ chối nó thì đang ép đặt tên xấu hơn cho vui.
    KHUON = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9][a-z0-9_]*)+$")
    for action, _tep, _ly_do in PHAI_CO_DAU_VET:
        assert KHUON.match(action), f"{action!r} không theo khuôn mien.doi_tuong.viec"
