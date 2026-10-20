"""Adapter Casbin CHỈ-ĐỌC, dựng policy từ các bảng RBAC đã chuẩn hoá.

Vì sao KHÔNG có bảng `casbin_rule`
----------------------------------
Adapter mặc định của Casbin lưu policy vào một bảng riêng (`casbin_rule`) với
cấu trúc `ptype, v0..v5`. Dùng nó ở đây sẽ tạo ra **nguồn sự thật thứ hai**
cho cùng một câu hỏi, và hai nguồn sự thật cho quyền là một loại lỗi rất khó
chịu: chúng trôi ra khỏi nhau dần dần, và cái sai thắng ở nơi nào tuỳ vào mã
nào đọc bảng nào.

Cụ thể hơn, ba thứ sẽ mất:

  * Khoá ngoại. `casbin_rule.v0 = 'user:abc'` là một chuỗi. Không gì bắt nó
    trỏ tới một tài khoản có thật, nên xoá tài khoản để lại policy mồ côi vẫn
    khớp — với một `user_id` mà tài khoản mới có thể tái dùng.
  * Vòng đời. Bảng đó không có `revoked_at`. Thu hồi là XOÁ dòng, nên lịch sử
    "ai từng có quyền gì" biến mất đúng lúc điều tra cần nó.
  * Bất biến. Không có gì ngăn một dòng gán role TENANT ở phạm vi PROJECT.
    Trigger `ct_*_scope` chỉ tồn tại trên các bảng gán thật.

Nên adapter này chỉ CHIẾU: đọc bảng chuẩn hoá, dựng ra p/g trong bộ nhớ. Bỏ
Casbin đi thì dữ liệu quyền còn nguyên và thay được bằng engine khác mà không
migrate lại bảng nào.

`save_policy` và họ hàng đều NÉM LỖI
-------------------------------------
Không phải `pass`. Một `save_policy` im lặng không làm gì sẽ khiến mọi lời gọi
`add_role_for_user()` trông như thành công và biến mất sau lần reload đầu tiên
— quyền được cấp qua giao diện, hoạt động vài phút, rồi tự bốc hơi. Ném lỗi
biến chuyện đó thành một dòng stack trace lúc phát triển.

Một bảng gán, không phải bốn
----------------------------
v1.0 có bốn bảng gán song song (`system_user_roles`, `tenant_member_roles`,
`workspace_member_roles`, `project_member_roles`); v5 gộp chúng thành một
`role_assignments`, và PHẠM VI của một lần gán được đọc từ `memberships` mà nó
trỏ tới, chứ không từ việc nó nằm ở bảng nào.

Đó là lý do `membership_id` NULL mang nghĩa dứt khoát: gán ở phạm vi hệ thống.
Trigger `ct_role_assignments_scope` cưỡng chế cả hai chiều — role SYSTEM không
được treo vào membership, và role không-SYSTEM bắt buộc phải có một cái.

Vì sao truy vấn lọc `revoked_at IS NULL` VÀ `status = 'ACTIVE'` VÀ `is_active`
-------------------------------------------------------------------------------
Ba điều kiện cho ba cách một quyền chấm dứt, và bỏ sót bất kỳ cái nào đều để
lại một đường cấp quyền sống dai:

    assignment.revoked_at   quyền bị thu hồi khỏi một người
    membership.status       người rời khỏi tenant (nhưng dòng gán còn đó)
    role.is_active          cả một role bị vô hiệu hoá

Trường hợp thứ hai là cái dễ quên nhất: gỡ MỀM ai đó (`status = 'REMOVED'`)
không tự động thu hồi assignment của họ. Không JOIN vào membership ở đây,
người đã bị gỡ vẫn giữ nguyên quyền.

Trường hợp thứ ba có HAI lớp, và cả hai đều cần: trigger
`ct_role_assignments_scope` từ chối một lần gán MỚI vào role đã tắt, còn bộ lọc
`r.is_active` ở đây loại những lần gán CŨ có từ trước khi role bị tắt. Chỉ có
trigger thì vai đã nghỉ vẫn cấp quyền cho người đang mang nó; chỉ có bộ lọc thì
giao diện cho gán một vai không bao giờ có hiệu lực.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from casbin.persist import Adapter

logger = logging.getLogger(__name__)

#: Tiền tố định danh trong policy. Tách namespace của chủ thể và của role, để
#: một `role_id` UUID không bao giờ khớp một `user_id` UUID nếu hai bảng tình
#: cờ sinh ra cùng giá trị.
SUBJECT_PREFIX = "user:"
ROLE_PREFIX = "role:"
API_KEY_PREFIX = "api:"

#: Domain chính tắc, §9.2.
DOMAIN_SYSTEM = "sys"
DOMAIN_TENANT = "ten:"
DOMAIN_WORKSPACE = "ws:"
DOMAIN_PROJECT = "prj:"


def subject(user_id: Any) -> str:
    return f"{SUBJECT_PREFIX}{user_id}"


def role_subject(role_id: Any) -> str:
    return f"{ROLE_PREFIX}{role_id}"


def tenant_domain(tenant_id: str) -> str:
    return f"{DOMAIN_TENANT}{tenant_id}"


def workspace_domain(workspace_id: Any) -> str:
    return f"{DOMAIN_WORKSPACE}{workspace_id}"


def project_domain(project_id: Any) -> str:
    return f"{DOMAIN_PROJECT}{project_id}"


# ---------------------------------------------------------------------------
# Truy vấn
# ---------------------------------------------------------------------------
#
# Viết ra thành hằng số chứ không nhúng trong hàm, để bộ test đọc được chúng
# và để một lần sửa điều kiện lọc hiện rõ trong diff.

_Q_ROLE_PERMISSIONS = """
SELECT rp.role_id::text AS role_id, rp.permission_code
  FROM role_permissions rp
  JOIN roles r       ON r.role_id = rp.role_id
  JOIN permissions p ON p.permission_code = rp.permission_code
 WHERE r.is_active AND p.is_active
"""

#: Gán ở phạm vi hệ thống: `membership_id IS NULL`.
#:
#: `u.is_active` được kiểm ở ĐÂY và KHÔNG ở ba truy vấn kia, và bất đối xứng đó
#: là chủ ý: một tài khoản bị khoá vẫn giữ vai trong tenant của họ (để danh
#: sách thành viên còn đọc được và để mở khoá không phải cấp lại quyền), nhưng
#: quyền toàn nền tảng thì không được tự sống lại theo.
_Q_SYSTEM_ASSIGNMENTS = """
SELECT a.user_id::text AS user_id, a.role_id::text AS role_id
  FROM role_assignments a
  JOIN roles r ON r.role_id = a.role_id
  JOIN users u ON u.id = a.user_id
 WHERE a.membership_id IS NULL
   AND a.revoked_at IS NULL AND r.is_active AND u.is_active
"""

#: Ba truy vấn dưới cùng một khuôn, khác nhau đúng ở `m.scope_level` và cột
#: định danh domain. Không gộp thành một truy vấn có `CASE`: bốn nhóm `g` được
#: nạp vào Casbin bằng bốn hàm dựng domain khác nhau, và một truy vấn trả về
#: domain đã ghép sẵn sẽ đẩy việc dựng chuỗi `ten:`/`ws:`/`prj:` xuống SQL —
#: nơi không ai kiểm được nó khớp với `scope_resolver`.
_Q_TENANT_ASSIGNMENTS = """
SELECT a.user_id::text AS user_id, a.role_id::text AS role_id, m.tenant_id
  FROM role_assignments a
  JOIN memberships m ON m.membership_id = a.membership_id
  JOIN roles r       ON r.role_id = a.role_id
 WHERE a.revoked_at IS NULL
   AND m.scope_level = 'TENANT'
   AND m.status = 'ACTIVE' AND m.left_at IS NULL
   AND r.is_active
"""

_Q_WORKSPACE_ASSIGNMENTS = """
SELECT a.user_id::text AS user_id, a.role_id::text AS role_id,
       m.workspace_id::text AS workspace_id
  FROM role_assignments a
  JOIN memberships m ON m.membership_id = a.membership_id
  JOIN roles r       ON r.role_id = a.role_id
 WHERE a.revoked_at IS NULL
   AND m.scope_level = 'WORKSPACE'
   AND m.status = 'ACTIVE' AND m.left_at IS NULL
   AND r.is_active
"""

_Q_PROJECT_ASSIGNMENTS = """
SELECT a.user_id::text AS user_id, a.role_id::text AS role_id,
       m.project_id::text AS project_id
  FROM role_assignments a
  JOIN memberships m ON m.membership_id = a.membership_id
  JOIN roles r       ON r.role_id = a.role_id
 WHERE a.revoked_at IS NULL
   AND m.scope_level = 'PROJECT'
   AND m.status = 'ACTIVE' AND m.left_at IS NULL
   AND r.is_active
"""

#: Đối chứng cho phép kiểm "policy có bị RLS cắt cụt không".
#:
#: `role_assignments` KHÔNG mang `tenant_id` nên không chịu RLS; hai bảng nó
#: JOIN sang thì có (`users`) hoặc chịu chính sách danh mục dùng chung
#: (`roles`). Nên số dòng thô ở đây là cận trên đúng, và một chênh lệch nghĩa là
#: phép JOIN đã lọc mất dòng.
_Q_SYSTEM_ASSIGNMENT_COUNT = """
SELECT count(*) AS n FROM role_assignments
 WHERE membership_id IS NULL AND revoked_at IS NULL
"""


class ReadOnlyPolicyAdapter(Adapter):
    """Chiếu các bảng RBAC thành policy Casbin. Không bao giờ ghi ngược."""

    def __init__(self) -> None:
        self.stats: dict[str, int] = {}

    # -- phần đọc ---------------------------------------------------------

    def load_policy(self, model) -> None:
        """Nạp toàn bộ policy đang hiệu lực vào `model`.

        Chạy trong **system scope**: nó phải thấy assignment của MỌI tenant để
        dựng được một enforcer dùng chung cho cả tiến trình. Đây là một lần
        vượt biên giới tenant có chủ ý, và nó nằm trong số ít lần được phép —
        cùng loại với vòng đồng bộ CSV→DB.

        Vì sao đọc hết chứ không lọc theo tenant: §21 Phase 1. Với quy mô hiện
        tại (chục tenant, trăm người) toàn bộ policy là vài nghìn dòng và vừa
        trong bộ nhớ thoải mái. Nạp theo tenant (Phase 2) là tối ưu hoá cho
        vấn đề chưa có, và nó kéo theo một tầng cache enforcer-theo-tenant với
        bài toán vô hiệu hoá riêng.
        """
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import in_system_scope, system_scope

        with system_scope("casbin: nap policy cho moi tenant"):
            # Khẳng định phạm vi thay vì tin vào context manager phía trên.
            #
            # Không thừa: `users`, `tenant_members` và bốn bảng gán đều chịu
            # RLS, nên một lượt nạp NGOÀI system scope không báo lỗi gì cả — nó
            # trả về policy CẮT CỤT. Đo được trên sản xuất 11/08, cùng truy vấn:
            #
            #     trong system scope : 4 dòng
            #     ngoài mọi phạm vi  : 0 dòng
            #
            # Ở chế độ `shadow` hậu quả là một baseline mismatch bị nhiễm bẩn;
            # ở `casbin` thì đó là 403 hàng loạt cho quản trị viên nền tảng.
            if not in_system_scope():
                raise RuntimeError(
                    "load_policy chay ngoai system scope — policy se bi RLS cat "
                    "cut trong im lang. Tu choi nap."
                )

            role_perms = _fetch_all(_Q_ROLE_PERMISSIONS)
            system = _fetch_all(_Q_SYSTEM_ASSIGNMENTS)
            tenant = _fetch_all(_Q_TENANT_ASSIGNMENTS)
            workspace = _fetch_all(_Q_WORKSPACE_ASSIGNMENTS)
            project = _fetch_all(_Q_PROJECT_ASSIGNMENTS)

            # Đối chiếu với số dòng THÔ của các lần gán phạm vi hệ thống —
            # `role_assignments` không có `tenant_id` nên không chịu RLS. Nếu
            # hai con số lệch nhau thì phép JOIN sang `users` — vốn CÓ chịu RLS
            # — đã lọc mất dòng, và policy đang thiếu quyền ở tầng nền tảng.
            #
            # Đây là lưới bắt chính xác sự cố đã quan sát được: một worker nạp
            # `sys=0` trong khi ba worker kia nạp `sys=4`, và không có gì báo.
            #
            # Lưới này CHỈ giăng ở phạm vi hệ thống, và đó là một giới hạn đã
            # biết: ba mức kia JOIN sang `memberships`, vốn chịu RLS, nên không
            # có cận trên nào đọc được mà không tự nó bị cắt cụt. Cái chặn thật
            # cho ba mức đó là `in_system_scope()` ngay bên trên.
            expected_system = _fetch_all(_Q_SYSTEM_ASSIGNMENT_COUNT)[0]["n"]

        if len(system) != expected_system:
            raise RuntimeError(
                f"policy phan quyen cat cut: nap duoc {len(system)}/{expected_system} "
                f"gan o pham vi he thong. Nguyen nhan thuong gap la RLS loc mat "
                f"dong khi pham vi chua duoc dat."
            )

        for row in role_perms:
            model.add_policy("p", "p", [role_subject(row["role_id"]), row["permission_code"]])

        self._add_grouping(model, system, lambda r: DOMAIN_SYSTEM)
        self._add_grouping(model, tenant, lambda r: tenant_domain(r["tenant_id"]))
        self._add_grouping(model, workspace, lambda r: workspace_domain(r["workspace_id"]))
        self._add_grouping(model, project, lambda r: project_domain(r["project_id"]))

        self.stats = {
            "role_permissions": len(role_perms),
            "system": len(system),
            "tenant": len(tenant),
            "workspace": len(workspace),
            "project": len(project),
        }
        logger.info(
            "[CASBIN] nap policy: %d p, %d g (sys=%d ten=%d ws=%d prj=%d)",
            len(role_perms),
            len(system) + len(tenant) + len(workspace) + len(project),
            len(system), len(tenant), len(workspace), len(project),
        )

    @staticmethod
    def _add_grouping(model, rows: Iterable[dict], domain_of) -> None:
        for row in rows:
            model.add_policy(
                "g", "g",
                [subject(row["user_id"]), role_subject(row["role_id"]), domain_of(row)],
            )

    # -- phần ghi: cố ý không có ------------------------------------------

    _READ_ONLY = (
        "PostgreSQL la nguon su that duy nhat cho du lieu phan quyen. "
        "Sua role/quyen bang cac bang RBAC roi phat su kien "
        "authorization.policy.changed; dung ghi nguoc tu Casbin."
    )

    def save_policy(self, model) -> bool:
        raise NotImplementedError(self._READ_ONLY)

    def add_policy(self, sec, ptype, rule) -> None:
        raise NotImplementedError(self._READ_ONLY)

    def remove_policy(self, sec, ptype, rule) -> None:
        raise NotImplementedError(self._READ_ONLY)

    def remove_filtered_policy(self, sec, ptype, field_index, *field_values) -> None:
        raise NotImplementedError(self._READ_ONLY)
