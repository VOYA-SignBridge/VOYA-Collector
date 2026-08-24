"""Danh mục quyền và role dựng sẵn — một nguồn sự thật, ba nơi tiêu thụ.

Vì sao danh mục là DỮ LIỆU PYTHON chứ không phải SQL viết tay
--------------------------------------------------------------
Ba nơi cần đúng cùng một danh sách và không được phép lệch nhau:

    1. Bảng `permissions` trong PostgreSQL — nguồn sự thật lúc chạy
    2. Hằng số mà router import để gọi `authorize(..., PERM_X, ...)`
    3. Bộ test khẳng định mọi quyền được kiểm ở đâu đó có tồn tại trong bảng

Nếu danh mục sống trong tệp `.sql`, nơi thứ hai phải gõ lại chuỗi bằng tay, và
một lỗi chính tả (`sample.anotate`) sinh ra một quyền KHÔNG AI CÓ — nghĩa là
endpoint đó từ chối tất cả mọi người, kể cả người đáng lẽ được phép. Đó là hỏng
theo hướng an toàn nhưng vẫn là hỏng, và nó chỉ lộ ra khi có người thử dùng
tính năng ấy.

Với danh mục ở đây, `PERM.SAMPLE_ANNOTATE` là một thuộc tính Python: gõ sai thì
`AttributeError` ngay lúc import, trước khi container báo sẵn sàng.

Cách đọc bảng quyền
-------------------
Mỗi quyền mang bốn thuộc tính, và ba trong bốn thay đổi hành vi lúc chạy:

``applicable_scope``  Quyết định CHUỖI DOMAIN mà `AuthorizationService` sẽ thử.
                      Quyền phạm vi PROJECT được kiểm ở `prj:P → ws:W → ten:T →
                      sys`; quyền phạm vi TENANT chỉ ở `ten:T → sys`. Đặt sai
                      giá trị này không làm hở quyền, nhưng làm quyền ở phạm vi
                      rộng bị kiểm ở phạm vi hẹp và luôn DENY.

``requires_passcode`` Sau khi ALLOW, còn phải xác nhận mã hành động cá nhân.
                      KHÔNG BAO GIỜ biến DENY thành ALLOW (§16).

``is_api_assignable`` Khoá API của tenant có được cầm quyền này không. Quyền
                      phạm vi SYSTEM không bao giờ được — và đó là một CHECK ở
                      cơ sở dữ liệu, không phải một quy ước ở đây.

``risk_level``        Chỉ để hiển thị và để `audit_log.is_sensitive` phân loại.
                      Không có hiệu lực cưỡng chế.

Vì sao mã quyền lấy từ bề mặt THẬT chứ không từ một bản thiết kế
-----------------------------------------------------------------
Mỗi mã dưới đây thay thế một phép kiểm CÓ THẬT đang chạy trong mã nguồn, và
cột "thay cho" trong chú thích nói rõ phép nào. Đó là điều kiện để shadow mode
có nghĩa: nếu danh mục chứa quyền mà hệ cũ không có khái niệm tương ứng, phép
so sánh cũ-mới không định nghĩa được và mismatch không phân định được.

Ba nguồn quyền cũ, và cả ba đều được ánh xạ hết:

    users.is_admin                    → role SYSTEM `platform_admin`
    tenant_members.role = 'admin'     → role TENANT  `tenant_administrator`
    tenant_members.role = 'editor'    → role TENANT  `tenant_editor`
    tenant_members.role IS NULL       → KHÔNG có role tenant nào

Dòng cuối là một trạng thái, không phải một lỗ hổng ánh xạ — xem
`RETIRED_BUILTIN_ROLES` bên dưới.

Liên quan: ``app/storage/authz_schema.py`` (schema), ``app/authorization/
authorization_service.py`` (nơi tiêu thụ), ``app/cli/backfill_authz.py``.
"""

from __future__ import annotations

from typing import NamedTuple

SYSTEM = "SYSTEM"
TENANT = "TENANT"
WORKSPACE = "WORKSPACE"
PROJECT = "PROJECT"

NORMAL = "NORMAL"
SENSITIVE = "SENSITIVE"
CRITICAL = "CRITICAL"


#: Loại tenant, khi một role bị ghim vào một loại. Xem `BuiltinRole.tenant_type`.
COMMUNITY = "COMMUNITY"
ORGANIZATION = "ORGANIZATION"


class Permission(NamedTuple):
    code: str
    scope: str
    description: str
    risk: str = NORMAL
    requires_passcode: bool = False
    api_assignable: bool = False
    #: Quyền này có được nằm trong một role do tenant tự tạo không (v5 §4).
    #:
    #: Mặc định TRUE, và cái đó là chủ ý — xem chú thích cùng chủ đề ở
    #: `authz_schema.py`. Đặt FALSE cho những quyền mà nếu tenant tự gói lại
    #: được thì họ có thể ỦY QUYỀN đi chính khả năng kiểm soát tenant, hoặc
    #: đụng tới bằng chứng pháp lý về người thật.
    #:
    #: Quyền phạm vi SYSTEM KHÔNG cần đặt tay: `_derive_custom_role_flags()`
    #: bên dưới ép chúng về FALSE, và cơ sở dữ liệu cũng có ràng buộc riêng
    #: (`ck_permissions_system_not_custom_role`). Hai lớp, vì một cái là quy
    #: ước trong mã còn cái kia đúng kể cả khi ai đó ghi thẳng vào bảng.
    custom_role_allowed: bool = True


# ---------------------------------------------------------------------------
# Danh mục
# ---------------------------------------------------------------------------
#
# Thứ tự: SYSTEM → TENANT → WORKSPACE → PROJECT, và trong mỗi nhóm thì đọc
# trước ghi. Giữ thứ tự này khi thêm quyền mới; nó là thứ làm cho bảng dài này
# còn duyệt bằng mắt được.

PERMISSIONS: tuple[Permission, ...] = (
    # --- SYSTEM: người vận hành nền tảng --------------------------------
    # Thay cho: `current_user["is_admin"]` ở routers/admin.py, tenants.py,
    # legal_admin.py, support.py, vocabulary.py.
    Permission("platform.user.read", SYSTEM,
               "Xem danh sách mọi tài khoản trên nền tảng"),
    Permission("platform.user.manage", SYSTEM,
               "Bật/tắt tài khoản, đổi cờ quản trị", CRITICAL, requires_passcode=True),
    Permission("platform.tenant.read", SYSTEM, "Xem mọi tenant"),
    Permission("platform.tenant.create", SYSTEM, "Tạo tenant mới", SENSITIVE),
    Permission("platform.tenant.suspend", SYSTEM,
               "Đình chỉ hoặc khôi phục một tenant", SENSITIVE),
    # Xoá vĩnh viễn dữ liệu của cả một tổ chức. Nếu chỉ MỘT quyền trong danh
    # mục này đáng đòi xác thực nâng cấp thì là quyền này.
    Permission("platform.tenant.purge", SYSTEM,
               "Xoá vĩnh viễn toàn bộ dữ liệu của một tenant",
               CRITICAL, requires_passcode=True),
    Permission("platform.role.manage", SYSTEM,
               "Cấp hoặc thu hồi quyền ở phạm vi hệ thống",
               CRITICAL, requires_passcode=True),
    Permission("platform.settings.manage", SYSTEM,
               "Đổi thiết lập toàn nền tảng", SENSITIVE),
    Permission("platform.plan.manage", SYSTEM, "Quản lý bảng giá và hạn mức", SENSITIVE),
    Permission("platform.legal.publish", SYSTEM,
               "Công bố văn bản pháp lý ràng buộc mọi người dùng",
               CRITICAL, requires_passcode=True),
    Permission("platform.audit.read", SYSTEM, "Đọc nhật ký kiểm toán ở tầng nền tảng"),
    Permission("platform.support.staff", SYSTEM,
               "Trả lời phiếu hỗ trợ với vai nhân viên"),
    # Thay cho: `vocabulary_registry.assert_system_admin`.
    Permission("platform.vocabulary.manage", SYSTEM,
               "Sửa danh mục từ vựng dùng chung của cộng đồng", SENSITIVE),

    # --- TENANT ----------------------------------------------------------
    Permission("tenant.read", TENANT, "Xem thông tin tenant", api_assignable=True),
    Permission("tenant.settings.manage", TENANT, "Đổi thiết lập của tenant", SENSITIVE),
    Permission("tenant.member.read", TENANT, "Xem danh sách thành viên"),
    Permission("tenant.member.invite", TENANT, "Mời người vào tenant", SENSITIVE),
    Permission("tenant.member.remove", TENANT, "Gỡ thành viên khỏi tenant", SENSITIVE),
    # Cấp quyền là thứ nhân bản chính nó: ai cấp được quyền thì cấp được quyền
    # cấp quyền. Đòi xác thực nâng cấp ở đây chặn được kịch bản phiên bị cướp
    # âm thầm tự nâng cấp rồi mở rộng ra.
    #
    # `custom_role_allowed=False` từ đây trở xuống, và lý do là chung: nếu
    # tenant gói được quyền này vào một role tự tạo thì họ ỦY QUYỀN ĐI được
    # chính khả năng kiểm soát tenant. Một "Research Lead" tự tạo mà cầm
    # `tenant.role.manage` có thể tự nâng mình lên Tenant Owner — và người tạo
    # ra role đó thường không nhận ra mình vừa làm gì.
    Permission("tenant.role.manage", TENANT,
               "Cấp hoặc thu hồi role trong tenant", CRITICAL,
               requires_passcode=True, custom_role_allowed=False),
    Permission("tenant.apikey.read", TENANT, "Xem danh sách khoá API"),
    Permission("tenant.apikey.manage", TENANT,
               "Tạo và thu hồi khoá API", CRITICAL,
               requires_passcode=True, custom_role_allowed=False),
    Permission("tenant.webhook.manage", TENANT, "Quản lý webhook", SENSITIVE),
    Permission("tenant.billing.read", TENANT, "Xem hoá đơn và đăng ký"),
    Permission("tenant.billing.manage", TENANT,
               "Đổi gói đăng ký và phương thức thanh toán",
               CRITICAL, requires_passcode=True, custom_role_allowed=False),
    Permission("tenant.export.create", TENANT,
               "Xuất toàn bộ dữ liệu của tenant", SENSITIVE, api_assignable=True),
    Permission("tenant.audit.read", TENANT, "Đọc nhật ký kiểm toán của tenant"),
    Permission("tenant.purge", TENANT,
               "Xoá vĩnh viễn dữ liệu của chính tenant này",
               CRITICAL, requires_passcode=True, custom_role_allowed=False),
    # Thay cho: `vocabulary_registry.assert_can_edit_registry` (EDITOR_ROLES).
    Permission("registry.read", TENANT, "Đọc danh mục lớp của tenant", api_assignable=True),
    Permission("registry.publish", TENANT,
               "Công bố một phiên bản danh mục mới", SENSITIVE),
    Permission("vocabulary.read", TENANT, "Đọc nhóm từ vựng và hồ sơ nhận dạng",
               api_assignable=True),
    Permission("vocabulary.manage", TENANT, "Sửa nhóm từ vựng, phương ngữ, hồ sơ"),
    Permission("signer.read", TENANT, "Xem danh sách người ký"),
    Permission("signer.manage", TENANT, "Thêm, sửa, gộp người ký", SENSITIVE),
    # Đồng thuận là bằng chứng pháp lý về người thật. Đọc nó là đọc dữ liệu cá
    # nhân, nên nó KHÔNG cấp được cho khoá API.
    Permission("consent.read", TENANT, "Xem trạng thái đồng thuận của người ký", SENSITIVE),
    # Đồng thuận là bằng chứng pháp lý về người thật, và `consent.manage` là
    # quyền ghi nhận/rút THAY cho họ. Nó không nằm trong role tự tạo được, vì
    # ai cầm nó có thể tạo ra hồ sơ đồng thuận mà chủ thể chưa từng đưa ra.
    Permission("consent.manage", TENANT,
               "Ghi nhận hoặc rút đồng thuận thay người ký", CRITICAL,
               custom_role_allowed=False),

    # --- WORKSPACE --------------------------------------------------------
    Permission("workspace.read", WORKSPACE, "Xem workspace", api_assignable=True),
    Permission("workspace.manage", WORKSPACE, "Sửa, lưu trữ, xoá workspace", SENSITIVE),
    Permission("workspace.member.manage", WORKSPACE,
               "Thêm/gỡ thành viên workspace", SENSITIVE),
    Permission("project.create", WORKSPACE, "Tạo project trong workspace"),

    # --- PROJECT ----------------------------------------------------------
    Permission("project.read", PROJECT, "Xem project", api_assignable=True),
    Permission("project.manage", PROJECT, "Sửa, lưu trữ, xoá project", SENSITIVE),
    Permission("project.member.manage", PROJECT, "Thêm/gỡ thành viên project", SENSITIVE),

    Permission("sample.read", PROJECT, "Đọc mẫu dữ liệu", api_assignable=True),
    Permission("sample.create", PROJECT, "Thu và nộp mẫu mới", api_assignable=True),
    Permission("sample.annotate", PROJECT, "Gán nhãn và sửa siêu dữ liệu của mẫu"),
    # Quyết định một mẫu có được dùng ngoài phạm vi người đóng góp hay không.
    #
    # SENSITIVE vì nó là cái nút biến dữ liệu riêng thành dữ liệu chung — cùng
    # hạng với `dataset.publish`, không phải với `sample.annotate`.
    #
    # Phạm vi PROJECT, và phạm vi ấy CHÍNH LÀ cấp bậc người duyệt: một vai
    # phạm vi rộng hơn mang theo mọi quyền PROJECT, nên
    # `tenant_administrator` duyệt được khắp tenant, `workspace_administrator`
    # duyệt trong workspace của mình và các project bên trong nó, còn
    # `project_administrator` / `project_reviewer` chỉ trong project của họ.
    # Không cần ba quyền riêng cho ba cấp — `scope_resolver` đã trả lời câu
    # "grant này với tới đâu".
    #
    # Người đóng góp KHÔNG tự duyệt dữ liệu của chính mình, và điều đó cần HAI
    # thứ chứ không phải một:
    #
    #   * không có hậu tố `.read`, nên `_read_only()` bỏ qua nó — các vai
    #     viewer và `community_member` không nhận;
    #   * có tên trong danh sách loại trừ của `_PROJECT_CONTRIBUTOR_PERMS`,
    #     phải viết TƯỜNG MINH vì tập đó được `_codes()` sinh ra và mọi quyền
    #     PROJECT mới tự chảy vào nếu không bị loại.
    Permission("sample.moderate", PROJECT,
               "Duyệt hoặc từ chối mẫu trước khi nó được dùng chung", SENSITIVE),
    # Thay cho: kiểm `is_owner or is_admin` ở routers/label_sessions.py.
    Permission("sample.delete", PROJECT, "Xoá mẫu của người khác", SENSITIVE),
    Permission("sample.export", PROJECT, "Tải mẫu thô ra ngoài", SENSITIVE,
               api_assignable=True),

    Permission("upload.create", PROJECT, "Tải video thô lên", api_assignable=True),
    Permission("upload.delete", PROJECT, "Xoá bản tải lên thô", SENSITIVE),

    Permission("class.read", PROJECT, "Xem lớp trong project", api_assignable=True),
    Permission("class.create", PROJECT, "Tạo lớp mới"),
    Permission("class.update", PROJECT, "Sửa nhãn, phương ngữ, hồ sơ của lớp"),
    Permission("class.delete", PROJECT, "Xoá lớp cùng toàn bộ mẫu của nó", SENSITIVE),

    Permission("dataset.read", PROJECT, "Đọc bộ dữ liệu", api_assignable=True),
    Permission("dataset.create", PROJECT, "Tạo bộ dữ liệu và nhánh"),
    Permission("dataset.publish", PROJECT, "Công bố một phiên bản bộ dữ liệu", SENSITIVE),
    Permission("dataset.delete", PROJECT, "Xoá bộ dữ liệu", SENSITIVE),

    Permission("training.read", PROJECT, "Xem tiến trình và kết quả huấn luyện",
               api_assignable=True),
    Permission("training.submit", PROJECT, "Gửi công việc huấn luyện"),
    Permission("training.cancel", PROJECT, "Huỷ công việc huấn luyện đang chạy"),
    Permission("training.promote", PROJECT,
               "Đưa một mô hình vào phục vụ nhận dạng", SENSITIVE),

    Permission("label_session.read", PROJECT, "Xem phiên gán nhãn"),
    Permission("label_session.manage", PROJECT,
               "Sửa hoặc xoá phiên gán nhãn của người khác", SENSITIVE),
)


class _Codes:
    """Truy cập mã quyền bằng thuộc tính, để lỗi chính tả là lỗi lúc import.

    `PERM.SAMPLE_DELETE` thay vì chuỗi `"sample.delete"` rải khắp router. Xem
    docstring module về vì sao chuỗi trần là kiểu hỏng im lặng.
    """

    def __init__(self, permissions: tuple[Permission, ...]) -> None:
        for perm in permissions:
            setattr(self, perm.code.replace(".", "_").upper(), perm.code)


PERM = _Codes(PERMISSIONS)

#: Tra cứu siêu dữ liệu theo mã. `AuthorizationService` đọc nó để biết chuỗi
#: domain và việc có cần mã hành động hay không, mà không phải hỏi cơ sở dữ
#: liệu ở mỗi request — bảng `permissions` vẫn là nguồn sự thật lúc chạy, và
#: `verify()` bên dưới khẳng định hai bên khớp nhau.
BY_CODE: dict[str, Permission] = {p.code: p for p in PERMISSIONS}


# ---------------------------------------------------------------------------
# Role dựng sẵn
# ---------------------------------------------------------------------------

class BuiltinRole(NamedTuple):
    #: Định danh ổn định. Xuất hiện NGUYÊN VĂN trong policy của Casbin và trong
    #: nhật ký kiểm toán, nên đổi nó là một câu migration, không phải đổi nhãn.
    code: str
    #: Nhãn hiển thị. Đổi tự do, không ai tham chiếu.
    name: str
    scope: str
    description: str
    permissions: tuple[str, ...]
    #: Ghim role vào một loại tenant (v5 §3). `None` = dùng được ở mọi loại.
    #: Chỉ hai role Community đặt giá trị này, và nó là thứ ngăn
    #: `community_curator` được gán trong một tenant tổ chức — nơi tập quyền
    #: được thiết kế cho không gian dùng chung sẽ mang ý nghĩa khác hẳn.
    tenant_type: str | None = None


def _codes(*, scope: str | None = None, exclude: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Mọi mã quyền, lọc theo phạm vi. Dùng để dựng role mà không gõ lại danh sách."""
    return tuple(
        p.code for p in PERMISSIONS
        if (scope is None or p.scope == scope) and p.code not in exclude
    )


#: Quyền chỉ-đọc, nhận diện bằng hậu tố. Dùng cho các role viewer.
#:
#: Dựa vào quy ước đặt tên chứ không vào một danh sách viết tay, để một quyền
#: đọc thêm sau này tự động vào role viewer thay vì bị bỏ quên ở đó — bỏ quên
#: theo hướng này tạo ra một viewer không xem được thứ mọi viewer khác xem
#: được, và triệu chứng là "giao diện trống" chứ không phải một lỗi.
def _read_only(scope: str) -> tuple[str, ...]:
    return tuple(
        p.code for p in PERMISSIONS
        if p.scope == scope and p.code.endswith((".read", ".list"))
    )


#: Tập quyền của người đóng góp trong một project. Tách thành hằng số vì BA
#: role dùng lại nó (`tenant_member`, `workspace_member`, `project_contributor`)
#: và ba bản sao chép tay sẽ lệch nhau ở lần sửa đầu tiên.
_PROJECT_CONTRIBUTOR_PERMS: tuple[str, ...] = _codes(
    scope=PROJECT,
    exclude=(PERM.PROJECT_MANAGE, PERM.PROJECT_MEMBER_MANAGE,
             PERM.DATASET_DELETE, PERM.CLASS_DELETE, PERM.TRAINING_PROMOTE,
             # Người đóng góp KHÔNG duyệt dữ liệu — kể cả của chính mình.
             #
             # Phải loại TƯỜNG MINH, vì tập này được SINH RA từ `_codes()` chứ
             # không viết tay: mọi quyền PROJECT mới đều tự chảy vào đây trừ
             # khi có tên trong danh sách loại trừ. Thêm `sample.moderate` mà
             # quên dòng này thì `project_contributor` và `community_curator`
             # lặng lẽ được quyền duyệt, và cả hai bài kiểm ở
             # `test_sample_review_status.py::TestAiDuocDuyet` sẽ đỏ — chúng
             # đỏ đúng chỗ này, ngày 21/08/2026.
             PERM.SAMPLE_MODERATE),
)

#: Quyền chỉ thuộc về CHỦ tenant, không thuộc quản trị viên.
#:
#: v5 §3 tách `tenant_owner` khỏi `tenant_administrator`, và đây là chỗ khác
#: nhau DUY NHẤT giữa hai role — hai vai không được trùng quyền, không thì việc
#: tách chúng ra chỉ là hai cái tên cho cùng một thứ.
#:
#: ĐÚNG HAI quyền, và ranh giới là "kết thúc hoặc định đoạt tenant" chứ không
#: phải "nhạy cảm". `tenant.settings.manage` từng nằm ở đây và đã được gỡ ra:
#: đổi thiết lập là việc VẬN HÀNH hằng ngày của quản trị viên, còn xoá sạch dữ
#: liệu và đổi hợp đồng thanh toán thì không.
_OWNER_ONLY_PERMS: tuple[str, ...] = (
    PERM.TENANT_PURGE,
    PERM.TENANT_BILLING_MANAGE,
)

BUILTIN_ROLES: tuple[BuiltinRole, ...] = (
    # --- SYSTEM ---------------------------------------------------------
    #
    # Cầm MỌI quyền ở mọi phạm vi — hợp lệ vì thống trị phạm vi cho phép role
    # rộng chứa quyền hẹp, và trigger `ct_role_permissions_dominance` kiểm đúng
    # chiều đó.
    #
    # Đây là ánh xạ trực tiếp của `users.is_admin = TRUE`, và nó CỐ Ý rộng đúng
    # bằng cờ cũ: shadow mode chỉ có nghĩa khi hai vế trả lời cùng câu hỏi. Thu
    # hẹp nó là việc của Phase D, sau khi mismatch suite đã sạch.
    BuiltinRole("platform_administrator", "Platform Administrator", SYSTEM,
                "Người vận hành nền tảng — thay cho cờ users.is_admin",
                _codes()),

    # Vai MỚI của v5. Đọc được mọi thứ ở tầng nền tảng, ghi được KHÔNG GÌ.
    # Tồn tại để việc rà soát tuân thủ không phải mượn tài khoản quản trị —
    # tức là để nhật ký kiểm toán phân biệt được "người đi xem" với "người
    # đi sửa".
    BuiltinRole("platform_auditor", "Platform Auditor", SYSTEM,
                "Rà soát và kiểm toán toàn nền tảng, không sửa được gì",
                _read_only(SYSTEM) + (PERM.TENANT_AUDIT_READ, PERM.TENANT_READ)),

    # --- COMMUNITY (tenant dự trữ) ---------------------------------------
    #
    # Hai role dưới đây bị ghim vào tenant COMMUNITY bằng `tenant_type`, và
    # trigger `ct_role_assignments_scope` từ chối nếu ai đó gán chúng ở nơi
    # khác. Phạm vi của chúng là TENANT — Community LÀ một tenant, không phải
    # một mức phạm vi thứ năm.
    BuiltinRole("community_member", "Community Member", TENANT,
                "Thành viên cộng đồng — mọi tài khoản mới nhận vai này",
                (
                    PERM.TENANT_READ,
                    PERM.REGISTRY_READ, PERM.VOCABULARY_READ,
                    PERM.WORKSPACE_READ, PERM.PROJECT_READ,
                    PERM.CLASS_READ, PERM.SAMPLE_READ, PERM.SAMPLE_CREATE,
                    PERM.UPLOAD_CREATE, PERM.LABEL_SESSION_READ,
                    PERM.DATASET_READ,
                ),
                tenant_type=COMMUNITY),

    BuiltinRole("community_curator", "Community Curator", TENANT,
                "Biên tập từ vựng và dữ liệu dùng chung của cộng đồng",
                (
                    PERM.TENANT_READ, PERM.TENANT_MEMBER_READ,
                    PERM.REGISTRY_READ, PERM.REGISTRY_PUBLISH,
                    PERM.VOCABULARY_READ, PERM.VOCABULARY_MANAGE,
                    PERM.SIGNER_READ,
                    PERM.WORKSPACE_READ,
                    # `PERM.PROJECT_READ` KHÔNG liệt kê ở đây: nó đã nằm trong
                    # `_PROJECT_CONTRIBUTOR_PERMS` bên dưới, và tự kiểm lúc
                    # import từ chối role có quyền trùng lặp.
                )
                + _PROJECT_CONTRIBUTOR_PERMS,
                tenant_type=COMMUNITY),

    # Người kiểm duyệt của cộng đồng. Chuyên gia được quản trị viên nền tảng
    # mời và cấp vai; KHÔNG phải một bậc của thang quản trị.
    #
    # Vì sao tách khỏi `community_curator` thay vì thêm quyền vào đó
    # --------------------------------------------------------------
    # Curator là vai BIÊN TẬP: nó mang `vocabulary.manage`, `registry.publish`
    # và cả bộ quyền đóng góp project. Người kiểm duyệt được mời để PHÁN XÉT
    # dữ liệu của người khác. Gộp hai việc lại là cho một người quyền sửa đúng
    # thứ họ đang duyệt, và ranh giới giữa người đóng góp với người kiểm duyệt
    # biến mất — cùng lý do `project_reviewer` tồn tại tách khỏi
    # `project_contributor`.
    #
    # KHÔNG có `sample.create`: nếu người kiểm duyệt cũng đóng góp thì họ giữ
    # thêm `community_member`, và hai vai cộng lại. Một vai vừa thu vừa duyệt
    # sẽ tự duyệt mẫu của chính mình mà không ai đọc ra điều đó từ tên vai.
    BuiltinRole("community_reviewer", "Community Reviewer", TENANT,
                "Chuyên gia duyệt dữ liệu cộng đồng trước khi công khai",
                (
                    PERM.TENANT_READ,
                    PERM.REGISTRY_READ, PERM.VOCABULARY_READ,
                    PERM.WORKSPACE_READ, PERM.PROJECT_READ,
                    PERM.CLASS_READ, PERM.SAMPLE_READ,
                    PERM.SAMPLE_MODERATE,
                    PERM.SIGNER_READ,
                    PERM.LABEL_SESSION_READ,
                    PERM.DATASET_READ,
                ),
                tenant_type=COMMUNITY),

    # --- TENANT ----------------------------------------------------------
    #
    # Chủ tenant. Backfill gán vai này theo `tenants.owner_user_id`, KHÔNG theo
    # `tenant_members.role` — không có giá trị 'owner' nào trong cột đó.
    BuiltinRole("tenant_owner", "Tenant Owner", TENANT,
                "Chủ sở hữu tenant — định đoạt gói, thiết lập và vòng đời tenant",
                _codes(scope=TENANT) + _codes(scope=WORKSPACE) + _codes(scope=PROJECT)),

    # Ánh xạ của `tenant_members.role = 'admin'`.
    #
    # KHÁC role cũ `tenant_admin` ở đúng ba quyền trong `_OWNER_ONLY_PERMS`, và
    # đó là một lần THU HẸP có chủ đích theo v5 §3 — quản trị viên vận hành
    # tenant, chủ sở hữu định đoạt nó. Thu hẹp chứ không nới, nên nó không tạo
    # ra đường truy cập mới cho ai.
    #
    # KHÔNG chứa quyền SYSTEM: quản trị viên tenant không phải quản trị viên
    # nền tảng, và trigger dominance sẽ từ chối nếu ai đó thử thêm.
    BuiltinRole("tenant_administrator", "Tenant Administrator", TENANT,
                "Quản trị viên của một tenant",
                _codes(scope=TENANT, exclude=_OWNER_ONLY_PERMS)
                + _codes(scope=WORKSPACE) + _codes(scope=PROJECT)),

    # Ánh xạ của `tenant_members.role = 'editor'` (EDITOR_ROLES trong
    # vocabulary_registry.py). Tập quyền GIỮ NGUYÊN từ role cũ, từng quyền một —
    # 6 người thật đang mang vai này, và mục tiêu của lượt di trú là không ai
    # đổi quyền.
    #
    # Vì sao GIỮ tên `tenant_editor` thay vì đổi sang `tenant_member` như v5:
    # "member" mô tả TƯ CÁCH THÀNH VIÊN, mà tư cách thành viên giờ đã do bảng
    # `memberships` biểu diễn. Một role tên `tenant_member` bên cạnh một bảng
    # `memberships` là hai thứ khác nhau mang cùng một cái tên — và người đọc
    # sau sẽ mất thời gian mỗi lần gặp. `editor` mô tả cái nó thật sự cấp:
    # quyền biên tập. Giữ tên cũ cũng có nghĩa là `role_id` không phải đổi.
    BuiltinRole("tenant_editor", "Tenant Editor", TENANT,
                "Người biên tập dữ liệu và danh mục của tenant",
                (
                    PERM.TENANT_READ,
                    PERM.REGISTRY_READ, PERM.REGISTRY_PUBLISH,
                    PERM.VOCABULARY_READ, PERM.VOCABULARY_MANAGE,
                    PERM.SIGNER_READ, PERM.SIGNER_MANAGE,
                    PERM.TENANT_MEMBER_READ,
                )
                + _codes(scope=WORKSPACE, exclude=(PERM.WORKSPACE_MANAGE,
                                                   PERM.WORKSPACE_MEMBER_MANAGE))
                # KHÔNG dùng `_PROJECT_CONTRIBUTOR_PERMS` ở đây, dù cái tên nghe
                # hợp hơn. Tập đó loại thêm `dataset.delete`, `class.delete` và
                # `training.promote` — ba quyền mà role cũ `tenant_editor` CÓ.
                # Dùng nó sẽ lấy mất ba quyền của 6 người đang mang vai này, và
                # một lần thu hẹp âm thầm giữa lượt đổi schema là thứ chỉ lộ ra
                # khi có người bấm nút xoá và nhận 403.
                + _codes(scope=PROJECT, exclude=(PERM.PROJECT_MANAGE,
                                                 PERM.PROJECT_MEMBER_MANAGE))),

    # KHÔNG có `tenant_viewer` ở đây, và chỗ trống này là chủ ý — xem
    # `RETIRED_BUILTIN_ROLES`. Chỉ-đọc toàn tenant là một TIỆN LỢI, không phải
    # một tầng của mô hình quyền; ai cần nó thì dựng bằng role tự tạo.

    # --- WORKSPACE --------------------------------------------------------
    #
    # Bốn role WORKSPACE/PROJECT dưới đây CHƯA được backfill gán cho ai (0 dòng
    # trên sản xuất). Chúng tồn tại để khi giao diện quản lý workspace/project
    # được bật, không phải vừa thiết kế role vừa sửa mã phân quyền cùng lúc.
    BuiltinRole("workspace_administrator", "Workspace Administrator", WORKSPACE,
                "Quản lý một workspace và các project trong đó",
                _codes(scope=WORKSPACE) + _codes(scope=PROJECT)),
    # Giữ nguyên tên VÀ tập quyền của role cũ. Bản trước đổi nó thành
    # `workspace_member` với 20 quyền — nới từ 7 lên 20 chỉ vì cái tên mới nghe
    # như một vai đóng góp. Không ai đang mang vai này, nên việc nới đó không
    # hại ai; nhưng nó cũng không mua được gì, và một lượt di trú không nên
    # thay đổi ý nghĩa của một role như tác dụng phụ của việc đổi tên.
    BuiltinRole("workspace_viewer", "Workspace Viewer", WORKSPACE,
                "Chỉ xem workspace và các project trong đó",
                _read_only(WORKSPACE) + _read_only(PROJECT)),

    # --- PROJECT ----------------------------------------------------------
    BuiltinRole("project_administrator", "Project Administrator", PROJECT,
                "Quản lý một project",
                _codes(scope=PROJECT)),
    BuiltinRole("project_contributor", "Project Contributor", PROJECT,
                "Đóng góp và gán nhãn dữ liệu trong project",
                _PROJECT_CONTRIBUTOR_PERMS),

    # Vai MỚI của v5. Duyệt chứ không tạo: gán nhãn lại và quản lý phiên gán
    # nhãn của người khác, nhưng KHÔNG thu mẫu mới và KHÔNG xoá.
    #
    # `SAMPLE_MODERATE` phải liệt kê TƯỜNG MINH ở đây. Tập quyền của vai này
    # được viết tay chứ không sinh bằng `_codes(scope=PROJECT)`, nên một quyền
    # PROJECT mới KHÔNG tự chảy vào — và vai này chính là "editor" trong quy
    # tắc "ở cấp project chỉ quản trị hoặc editor mới được duyệt".
    BuiltinRole("project_reviewer", "Project Reviewer", PROJECT,
                "Duyệt và sửa nhãn dữ liệu do người khác đóng góp",
                _read_only(PROJECT) + (
                    PERM.SAMPLE_ANNOTATE,
                    PERM.SAMPLE_MODERATE,
                    PERM.CLASS_UPDATE,
                    PERM.LABEL_SESSION_MANAGE,
                )),
    BuiltinRole("project_viewer", "Project Viewer", PROJECT,
                "Chỉ xem dữ liệu trong project",
                _read_only(PROJECT)),
)

#: Role dựng sẵn ĐÃ BỊ GỠ khỏi danh mục, liệt kê tường minh.
#:
#: Vì sao một DANH SÁCH VIẾT TAY chứ không suy ra "role nào trong bảng mà không
#: có trong `BUILTIN_ROLES`"
#: -----------------------------------------------------------------------
#: Vì hai lý do khiến một role vắng mặt trong danh mục, và chúng đòi hai xử lý
#: ngược nhau:
#:
#:     GỠ HẲN     vai không còn tồn tại  → phải vô hiệu hoá
#:     ĐỔI TÊN    vai còn nguyên         → assignment cũ phải được DI TRÚ trước
#:
#: Suy ra tự động không phân biệt được hai cái đó. Cơ sở dữ liệu đang chạy vẫn
#: mang tên cũ (`tenant_admin`, `project_manager`) trong khi danh mục ở đây đã
#: sang tên v5 (`tenant_administrator`, `project_contributor`); một bước "vô
#: hiệu hoá mọi role lạ" sẽ tắt `tenant_admin` cùng 4 assignment đang sống của
#: nó, ngay trong lượt khởi động kế tiếp, mà không ai yêu cầu.
#:
#: Nên: vắng mặt KHÔNG có nghĩa gì cả; chỉ tên nằm ở đây mới bị vô hiệu hoá.
#:
#: Vì sao `tenant_viewer` ở đây
#: -----------------------------
#: Nó là một TIỆN LỢI — "chỉ đọc toàn tenant" — chứ không phải một tầng của mô
#: hình quyền, và nó gộp bốn phép đọc không hề hiền vào cùng một cái tên nghe
#: như hiền: `tenant.billing.read`, `tenant.audit.read`, `tenant.apikey.read`,
#: và `consent.read` (bằng chứng pháp lý về người thật). Tập quyền của nó do
#: `_read_only(TENANT)` sinh ra theo HẬU TỐ, nên mọi quyền `.read` phạm vi
#: TENANT thêm sau này sẽ tự động chảy vào mà không ai duyệt.
#:
#: Đo trên sản xuất 11/08/2026 trước khi gỡ: **0 assignment**, 0 dòng trong
#: `tenant_members` mang vai 'viewer'. Nên đây không phải một lần thu hẹp quyền
#: của ai — không có ai.
#:
#: Ai cần chỉ-đọc toàn tenant thì Tenant Owner/Admin dựng một role tự tạo từ
#: các quyền mà nền tảng cho phép (`custom_role_allowed`). Đó là đúng chỗ cho
#: nó: một lựa chọn của tổ chức, có người ký tên, chứ không phải một mặc định
#: của nền tảng mà không ai nhớ mình đã bật.
#:
#: KHÔNG hard-delete. `seed.py` chỉ đặt `is_active = FALSE`; dòng `roles` và 16
#: dòng `role_permissions` của nó ở lại để còn trả lời được "vai này từng cấp
#: gì". Xoá hẳn là việc của một migration riêng, sau khi xác minh mọi tham
#: chiếu = 0.
RETIRED_BUILTIN_ROLES: tuple[str, ...] = (
    "tenant_viewer",
)

#: Ánh xạ `tenant_members.role` cũ → mã role dựng sẵn. Backfill và shadow mode
#: đọc CÙNG hằng số này, nên chúng không thể bất đồng về việc "editor cũ tương
#: đương role nào".
#:
#: HAI khoá, không phải ba. `tenant_members.role IS NULL` — tư cách thành viên
#: có, vai ở tầng tenant không — là một trạng thái HỢP LỆ và cố ý không có mặt
#: ở đây: nó không ánh xạ sang role nào, nên nó không cấp gì ở phạm vi tenant.
#: Người như vậy chỉ nhận quyền qua assignment ở workspace/project.
#:
#: Đừng thêm `"viewer"` trở lại để "cho đủ". Cột `role` không còn nhận giá trị
#: đó (ràng buộc `tenant_members_role_valid`), và một khoá trỏ tới role đã bị
#: vô hiệu hoá sẽ làm `backfill_authz` dừng với "thiếu role dựng sẵn".
LEGACY_TENANT_ROLE_MAP: dict[str, str] = {
    "admin": "tenant_administrator",
    "editor": "tenant_editor",
}

#: Role mà `users.is_admin = TRUE` được ánh xạ sang.
LEGACY_SYSTEM_ADMIN_ROLE = "platform_administrator"

#: Role gán theo `tenants.owner_user_id`. Không có vai 'owner' nào trong
#: `tenant_members.role`, nên đây là nguồn DUY NHẤT để biết ai là chủ tenant.
LEGACY_TENANT_OWNER_ROLE = "tenant_owner"

#: Role mà mọi tài khoản mới nhận trong tenant cộng đồng (v5 §1, §18).
COMMUNITY_DEFAULT_ROLE = "community_member"

#: Tra cứu role dựng sẵn theo mã.
BUILTIN_BY_CODE: dict[str, BuiltinRole] = {r.code: r for r in BUILTIN_ROLES}


def custom_role_allowed(code: str) -> bool:
    """Quyền này có được nằm trong role do tenant tự tạo không.

    Quyền phạm vi SYSTEM luôn FALSE bất kể cờ trong danh mục — hai lớp cho cùng
    một bất biến, vì cái ở đây là quy ước trong mã còn ràng buộc
    `ck_permissions_system_not_custom_role` đúng kể cả khi ai đó ghi thẳng vào
    bảng.
    """
    perm = BY_CODE[code]
    return perm.custom_role_allowed and perm.scope != SYSTEM


# ---------------------------------------------------------------------------
# Tự kiểm lúc import
# ---------------------------------------------------------------------------
#
# Chạy ở mức module chứ không trong test, vì cả ba lỗi dưới đây tạo ra một hệ
# thống KHỞI ĐỘNG ĐƯỢC nhưng từ chối sai người, và triệu chứng (403 ở một
# endpoint) không chỉ về đây.

_SCOPE_RANK = {SYSTEM: 4, TENANT: 3, WORKSPACE: 2, PROJECT: 1}

for _role in BUILTIN_ROLES:
    for _code in _role.permissions:
        if _code not in BY_CODE:
            raise ValueError(
                f"role dung san {_role.code!r} tham chieu quyen khong ton tai: {_code!r}"
            )
        # Cùng bất biến mà trigger `ct_role_permissions_dominance` cưỡng chế,
        # kiểm ở đây để lỗi lộ ra lúc import chứ không phải lúc seed — seed
        # chạy trong `_run_ddl`, và `_run_ddl` nuốt lỗi.
        if _SCOPE_RANK[_role.scope] < _SCOPE_RANK[BY_CODE[_code].scope]:
            raise ValueError(
                f"role dung san {_role.code!r} (pham vi {_role.scope}) khong duoc chua "
                f"quyen {_code!r} (pham vi {BY_CODE[_code].scope})"
            )

    # Role dựng sẵn KHÔNG bị `is_custom_role_allowed` giới hạn — cờ đó chỉ áp
    # cho role do tenant tự tạo. Khẳng định ở đây để người đọc sau không "sửa"
    # nhầm bằng cách gỡ `tenant.purge` khỏi `tenant_owner`.
    if _role.tenant_type is not None and _role.scope != TENANT:
        raise ValueError(
            f"role dung san {_role.code!r} ghim vao loai tenant nhung pham vi la "
            f"{_role.scope} — chi role TENANT moi ghim duoc"
        )
    if len(set(_role.permissions)) != len(_role.permissions):
        raise ValueError(f"role dung san {_role.code!r} co quyen trung lap")

if len(BY_CODE) != len(PERMISSIONS):  # pragma: no cover - import guard
    raise ValueError("danh muc quyen co ma trung lap")

# Mã role dựng sẵn duy nhất TOÀN CỤC, không theo phạm vi — khớp chỉ mục
# `uq_roles_builtin_code`. Kiểm theo (phạm vi, mã) như bản trước sẽ CHO QUA hai
# role trùng mã khác phạm vi, rồi seed mới vỡ khi va vào chỉ mục ở cơ sở dữ liệu.
_builtin_codes = [r.code for r in BUILTIN_ROLES]
if len(set(_builtin_codes)) != len(_builtin_codes):  # pragma: no cover - import guard
    raise ValueError("hai role dung san trung ma")

# Một tên không thể vừa còn sống vừa đã nghỉ. Nếu ai đó thêm lại `tenant_viewer`
# vào `BUILTIN_ROLES` mà quên gỡ khỏi `RETIRED_BUILTIN_ROLES`, seed sẽ tạo nó
# rồi tắt nó ngay trong cùng một lượt — một role tồn tại, đúng tập quyền, và
# không cấp gì cho ai. Không có triệu chứng nào ngoài 403.
_retired_and_alive = set(RETIRED_BUILTIN_ROLES) & set(_builtin_codes)
if _retired_and_alive:  # pragma: no cover - import guard
    raise ValueError(
        f"role vua o BUILTIN_ROLES vua o RETIRED_BUILTIN_ROLES: "
        f"{', '.join(sorted(_retired_and_alive))}"
    )

# Mọi tên trong ba hằng số ánh xạ phải trỏ tới role có thật. Sai chính tả ở đây
# tạo ra một backfill chạy xong mà không gán gì, và không báo lỗi gì.
for _target in (
    *LEGACY_TENANT_ROLE_MAP.values(),
    LEGACY_SYSTEM_ADMIN_ROLE,
    LEGACY_TENANT_OWNER_ROLE,
    COMMUNITY_DEFAULT_ROLE,
):
    if _target not in BUILTIN_BY_CODE:  # pragma: no cover - import guard
        raise ValueError(f"anh xa tro toi role dung san khong ton tai: {_target!r}")
