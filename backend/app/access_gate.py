"""Ai chạm được endpoint nào — mặc định TỪ CHỐI, ngoại lệ phải khai báo.

Vì sao lật ngược
----------------
Trước 2026-08-07 mỗi endpoint TỰ CHỌN bật xác thực bằng cách thêm
``Depends(get_current_user)``. Kiểu thất bại của thiết kế đó là **bỏ sót**, và
một lần quét toàn bộ bề mặt tìm ra tám chỗ bỏ sót — trong đó có hai chỗ trả về
tên thật của người đóng góp và hai chỗ cho khách vãng lai tạo lớp mới.

Vá từng chỗ sẽ đúng hôm nay và hở lại ở endpoint tiếp theo. Nên quy tắc đảo lại:
mọi thứ đóng, ngoại lệ nằm trong hai tập hợp dưới đây, và một test khẳng định bề
mặt công khai thật sự KHỚP với chúng. Cùng hình dạng với allowlist ``system_scope``
ở ``test_tenant_isolation.py``: thêm ngoại lệ thì được, thêm mà không ai để ý thì
không.

Vì sao là middleware chứ không phải ``dependencies=`` trên router
------------------------------------------------------------------
``main.py`` mount MỖI router HAI LẦN — một lần ở gốc cho tương thích ngược, một
lần dưới ``/api/v1``. Đó là 18 lời gọi ``include_router``; gắn dependency vào
từng lời gọi nghĩa là 18 cơ hội bỏ sót, và lần mount thứ 19 thêm sau sẽ không có
gì nhắc. Một middleware phủ mọi đường, kể cả đường thêm sau khi file này được
viết.

Cái giá: middleware chạy TRƯỚC định tuyến, nên không đọc được template của route
(``/classes/{uid}``) mà chỉ đọc được đường thật. Vì vậy mọi mục trong danh sách
phải là đường **nguyên văn**, và ``test_no_public_route_is_parameterised`` ghim
điều đó — một đường có ``{`` trong danh sách sẽ không bao giờ khớp và sẽ âm thầm
bị đóng.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

#: Tiền tố phiên bản. Đường `/api/v1/x` và `/x` là CÙNG một endpoint, nên chuẩn
#: hoá về một dạng trước khi so — nếu không, đóng đường có phiên bản mà quên
#: đường không phiên bản là một lỗ mở toang.
_VERSION_PREFIX = "/api/v1"


def canonical(path: str) -> str:
    """Đưa một đường về dạng duy nhất để so sánh.

    Bỏ tiền tố phiên bản và dấu `/` cuối. `/api/v1/health/` và `/health` đều
    thành `/health`.
    """
    # Tiền tố chỉ được cắt khi nó là một ĐOẠN đường trọn vẹn. `startswith` trần
    # biến `/api/v10/x` thành `0/x` — một đường méo, không khớp gì, và bị 401.
    # Hỏng theo hướng an toàn, nhưng vẫn hỏng, và một đoạn tiền tố khác trong
    # tương lai có thể không may mắn như vậy.
    if path == _VERSION_PREFIX:
        path = "/"
    elif path.startswith(_VERSION_PREFIX + "/"):
        path = path[len(_VERSION_PREFIX):]
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path or "/"


#: Mở cho tất cả, không điều kiện.
#:
#: Mỗi mục ở đây là một quyết định phải giải thích được. Chỉ ba nhóm đủ tư cách:
#: thư viện công khai, khởi tạo phiên (không thể đòi đăng nhập để đăng nhập), và
#: những đường hạ tầng gọi từ bên trong mạng docker.
PUBLIC_ROUTES: frozenset[tuple[str, str]] = frozenset({
    # --- Thư viện công khai: XEM, không sửa ---
    ("GET", "/classes/list"),
    ("GET", "/dataset/labels"),
    ("GET", "/vocabulary/registry"),
    # Chỉ số tổng hợp. Nói được quy mô dự án mà không định danh ai:
    # {"labels_count":63,"total_samples":3860,"contributors_count":15}
    ("GET", "/classes/community-stats"),

    # Bảng giá. Thông tin thương mại công khai: bắt đăng nhập mới xem được giá
    # là chặn đúng người đang cân nhắc dùng sản phẩm. Chỉ trả về gói có
    # `is_listed`, nên `internal` — gói của tenant gốc — không lộ ra.
    ("GET", "/billing/plans"),

    # --- Xin phiếu dùng thử: phải mở, vì đây là cách xin ---
    ("POST", "/trial/start"),
    ("GET", "/trial/status"),

    # --- Văn bản pháp lý: phải đọc được TRƯỚC khi có tài khoản ---
    # Route thật là `/legal/{kind}`; cổng khớp ĐƯỜNG chứ không khớp template,
    # nên từng giá trị hợp lệ phải có mặt ở đây. Một `kind` mới thêm vào
    # `legal.KINDS` mà quên dòng tương ứng sẽ bị 401 — hỏng theo hướng an toàn,
    # và `test_every_legal_kind_is_publicly_readable` bắt được.
    #
    # Số hiệu phiên bản đi qua tham số TRUY VẤN (`?version=1.0`) chứ không phải
    # một đoạn đường, chính vì ràng buộc đường-nguyên-văn ở đây: `/legal/terms/
    # content` khai báo được, `/legal/terms/versions/1.0` thì không.
    ("GET", "/legal/documents"),
    ("GET", "/legal/terms"),
    ("GET", "/legal/privacy"),
    ("GET", "/legal/data_contribution"),
    ("GET", "/legal/guardian"),
    ("GET", "/legal/terms/content"),
    ("GET", "/legal/privacy/content"),
    ("GET", "/legal/data_contribution/content"),
    ("GET", "/legal/guardian/content"),
    # Tệp gốc (pdf/docx) của bản văn. Công khai cùng lý do như `/content`: phải
    # đọc được TRƯỚC khi tạo tài khoản. Gác nó sau cổng đăng nhập nghĩa là bắt
    # người ta đồng ý với thứ họ chưa mở ra được.
    ("GET", "/legal/terms/file"),
    ("GET", "/legal/privacy/file"),
    ("GET", "/legal/data_contribution/file"),
    ("GET", "/legal/guardian/file"),

    # --- Khởi tạo phiên ---
    ("POST", "/auth/login"),
    ("POST", "/auth/register"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),
    ("POST", "/auth/forgot-password"),
    ("POST", "/auth/reset-password"),
    ("POST", "/auth/recover/start"),
    ("POST", "/auth/recover/verify"),
    ("POST", "/auth/recover/confirm"),
    # Biểu mẫu đăng ký cần đọc lời mời trước khi tài khoản tồn tại.
    ("POST", "/tenants/invitations/inspect"),

    # --- Hạ tầng, gọi từ trong mạng docker ---
    # Healthcheck của container gọi 127.0.0.1; Prometheus scrape /metrics.
    # Cả hai PHẢI mở nếu không container báo unhealthy và giám sát chết.
    # Chặn từ bên ngoài là việc của nginx, không phải của tầng này.
    ("GET", "/health"),
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("GET", "/metrics"),
})

#: Mô hình nhận diện: CHẤP NHẬN phiên đăng nhập HOẶC phiếu dùng thử còn hạn.
#:
#: Tách khỏi PUBLIC_ROUTES vì đây là đường duy nhất tốn tài nguyên mà người chưa
#: đăng nhập chạm được. Đo 2026-08-07: 40 ms CPU mỗi lượt, không dùng GPU. Rẻ,
#: nhưng không miễn phí — và nó cũng là bề mặt để rút mô hình (ATLAS AML.T0024).
TRIAL_OR_SESSION_ROUTES: frozenset[tuple[str, str]] = frozenset({
    ("POST", "/realtime/predict"),
    ("GET", "/realtime/models"),
    ("GET", "/realtime/health"),
    ("GET", "/inference/classes"),
    ("GET", "/tts/voices"),
    ("POST", "/tts/speak"),
})

#: Trong nhóm trên, chỉ những đường này TIÊU hạn ngạch.
#:
#: Phần còn lại là siêu dữ liệu rẻ tiền — danh sách mô hình, danh sách giọng
#: đọc — mà giao diện nạp một lần khi mở trang. Tính chúng vào hạn ngạch nghĩa
#: là người dùng mất một phút chỉ vì mở trang và chưa ký gì cả, và đồng hồ bắt
#: đầu chạy trước khi họ nhận được bất cứ thứ gì.
#:
#: Chúng vẫn ĐÒI phiếu: không có phiếu thì không có gì để hiển thị.
TRIAL_CONSUMING_ROUTES: frozenset[tuple[str, str]] = frozenset({
    ("POST", "/realtime/predict"),
    ("POST", "/tts/speak"),
})


# ---------------------------------------------------------------------------
# Cổng thứ hai: thành viên KHÔNG CÓ vai ở tầng tenant
# ---------------------------------------------------------------------------
#
# `tenant_members.role IS NULL` nghĩa là: tư cách thành viên đang hoạt động,
# KHÔNG có grant nào ở phạm vi tenant. Nó KHÔNG có nghĩa "chỉ đọc" — đó là một
# phát biểu về AUTHORIZATION, không phải về tập thao tác. Người như vậy vẫn có
# thể nhận quyền ghi qua assignment ở workspace/project hoặc qua role tự tạo,
# và khi Casbin cầm quyền quyết định thì những đường đó có hiệu lực bình thường.
#
# Vì sao vẫn cần một cổng chặn thô ở đây
# ---------------------------------------
# Vì hôm nay `AUTHZ_MODE=shadow`: Casbin chỉ QUAN SÁT, hệ cũ quyết định. Mà hệ
# cũ chỉ biết đọc `tenant_members.role`, và chỉ đúng HAI chỗ hỏi nó —
# `routers/tenants.py::require_tenant_admin` và
# `vocabulary_registry.assert_can_edit_registry`. Mọi route ghi khác — thu mẫu,
# tải video, gửi huấn luyện, xoá bộ dữ liệu — KHÔNG hỏi vai gì cả.
#
# Nghĩa là nếu không có cổng này, lời mời "không vai" đầu tiên sẽ tạo ra một
# tài khoản ghi được gần như mọi thứ, trong khi giao diện nói họ chưa được cấp
# vai nào. Đó là fail-OPEN, và nó xuất hiện đúng vào lúc tính năng mới được bật.
#
# Cổng này là hàng rào TẠM. Nó biến mất ở Phase D, khi các route đó gọi
# `authorize()` và Casbin trả lời thật — lúc đó grant ở workspace/project mới
# thực sự dùng được. Cho tới lúc ấy: không grant tenant thì không ghi.

#: Không gian tên mà vai ở tầng tenant KHÔNG áp dụng: người dùng thao tác trên
#: CHÍNH TÀI KHOẢN của họ.
#:
#: Khớp theo TIỀN TỐ, khác với `PUBLIC_ROUTES` vốn khớp nguyên văn, và khác biệt
#: đó là chủ ý: đây là mặt phẳng DANH TÍNH, nơi mọi endpoint theo định nghĩa nói
#: về chủ thể đang gọi. Một endpoint mới dưới `/auth/` là một thao tác tự phục
#: vụ mới, và bắt nó phải xin vai tenant sẽ khoá người ta ra khỏi chính tài
#: khoản mình — kể cả việc đăng xuất hay bật 2FA.
#:
#: Mọi thứ NGOÀI danh sách này đều bị từ chối. Thêm một tiền tố ở đây là mở một
#: đường ghi cho người chưa được cấp vai; phải trả lời được câu "thao tác này có
#: chỉ chạm tới dữ liệu của chính người gọi không?".
SELF_SERVICE_WRITE_PREFIXES: tuple[str, ...] = (
    "/auth/",            # đăng xuất, đổi mật khẩu, phiên, 2FA, mã khôi phục
    "/account/",         # hồ sơ cá nhân
    "/verification/",    # xác minh email và số điện thoại
    "/trial/",           # phiếu dùng thử gắn với chính người gọi
    "/notifications/",   # đánh dấu đã đọc thông báo CỦA MÌNH
    "/support/",         # gửi phiếu hỗ trợ và trả lời trong phiếu của mình
)

#: Hành động đồng thuận, khớp theo ĐUÔI đường dẫn dưới `/legal/`.
#:
#: Đường thật là `/legal/{kind}/accept` và `/legal/{kind}/withdraw` — `kind` là
#: một đoạn Ở GIỮA, nên không có tiền tố nào phủ được chúng. Bản đầu của danh
#: sách trên ghi `"/legal/accept"` và nó khớp KHÔNG GÌ CẢ: mọi lần chấp nhận
#: điều khoản của một thành viên chưa có vai đều bị 403, tức là họ không bao giờ
#: qua nổi cổng đồng thuận để trở thành người dùng bình thường.
#:
#: Hai hành động này phải mở, và lý do sâu hơn tiện lợi: đồng thuận là quyết
#: định của CHÍNH CHỦ THỂ về dữ liệu của họ. Bắt nó phải xin một vai tenant là
#: đặt quyền tự quyết ấy dưới quyền của người khác — sai cả về pháp lý lẫn về
#: mô hình. `withdraw` càng phải mở: rút đồng thuận không bao giờ được khó hơn
#: cho đồng thuận.
#: Duong tu phuc vu khop CHINH XAC, khong theo tien to.
#:
#: `/tenants/invitations/accept` la hanh dong cua CHINH nguoi duoc moi: ho doi
#: mot lien ket lay tu cach thanh vien. Bat no phai co san mot vai tenant la mot
#: vong lap kin — vai la thu ma chinh loi moi nay cap. Cung hinh dang be tac voi
#: `/legal/{kind}/accept` ghi ngay tren.
#:
#: Vi sao KHONG dat `/tenants/` vao danh sach tien to: lam vay se mien tru moi
#: thao tac ghi cua quan tri to chuc — tao/xoa to chuc, doi vai, moi nguoi, xoa
#: sach du lieu. Mot dong cho tien loi doi lay ca mot mat phang quyen.
#:
#: Va vi sao khop CHINH XAC chu khong phai tien to cua rieng duong nay: mot
#: `/tenants/invitations/accept-all` them vao sau nay se im lang thua ke mien
#: tru nay ma khong ai xet lai.
SELF_SERVICE_EXACT_PATHS: frozenset = frozenset({
    "/tenants/invitations/accept",
    # Đổi tổ chức đang xem. Chỉ ghi MỘT cột trên hàng `users` của chính người
    # gọi, và chỉ sau khi `set_active_tenant` xác nhận họ là thành viên đang
    # hoạt động của tổ chức đích — nên nó không cấp thêm gì mà tư cách thành
    # viên chưa cấp.
    #
    # Phải miễn ở đây vì cùng lý do như `/tenants/invitations/accept`: đòi một
    # vai ở tầng tenant để được XEM tổ chức mình đã thuộc về là một cái bẫy
    # ngược — người chưa có vai không chuyển sang nổi tổ chức nơi họ có vai.
    "/tenants/switch",
})

SELF_SERVICE_LEGAL_ACTIONS: tuple[str, ...] = ("/accept", "/withdraw")

#: Phương thức KHÔNG đổi trạng thái. Chỉ những phương thức ngoài tập này mới đi
#: qua phép kiểm vai — một thành viên không vai vẫn đọc được bình thường.
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _is_self_service_write(path: str) -> bool:
    if path in SELF_SERVICE_EXACT_PATHS:
        return True
    if any(path.startswith(p) for p in SELF_SERVICE_WRITE_PREFIXES):
        return True
    return path.startswith("/legal/") and path.endswith(SELF_SERVICE_LEGAL_ACTIONS)


def _has_any_tenant_grant(user) -> bool:
    """Tài khoản này có vai ở tầng tenant ở BẤT KỲ tenant nào không.

    Vì sao "bất kỳ" chứ không "tenant của request này"
    ---------------------------------------------------
    Vì middleware không biết request này nói về tenant nào, và đoán thì sai.
    Bản đầu hỏi vai trong tenant NHÀ (`users.tenant_id`), và nó chặn nhầm ngay
    ca dùng phổ biến nhất: một người là quản trị viên của tenant B trong khi
    nhà của họ ở tenant A. `POST /tenants/B/invitations` của họ bị 403 dù họ có
    đúng quyền — `require_tenant_admin` ở tầng router mới là chỗ biết B là B.

    Phần lớn route ghi thậm chí KHÔNG nêu tenant nào trong đường dẫn (thu mẫu,
    tải video, huấn luyện): chúng ghi vào tenant nhà, do RLS quyết định. Nên
    "tenant của request" không phải một khái niệm mà tầng này đọc được.

    Câu hỏi mà cổng này trả lời được, và là câu đủ cho việc nó cần làm: *tài
    khoản này đã từng được cấp một vai ở tầng tenant chưa?* Ai chưa từng — thành
    viên mới được mời không kèm vai, hoặc tài khoản không thuộc tenant nào — thì
    không ghi. Ai có rồi thì đi tiếp, và các phép kiểm THẬT ở tầng router
    (`require_tenant_admin`, `assert_can_edit_registry`) quyết định họ được làm
    gì với tenant nào.

    Đây là hàng rào THÔ có chủ ý. Nó chặn đúng một trạng thái mới —
    "không grant nào cả" — chứ không thay thế phân quyền.

    Quản trị viên nền tảng qua vì họ CÓ quyền ở phạm vi hệ thống — KHÔNG phải
    vì họ thiếu tư cách thành viên
    -------------------------------------------------------------------------
    Phân biệt này quan trọng, và nó là ranh giới giữa một cổng đúng và một lỗ.
    "Thiếu membership" KHÔNG BAO GIỜ là lý do để cho qua: một tài khoản không
    thuộc tenant nào rơi vào nhánh cuối cùng và bị từ chối, y như một thành viên
    chưa có vai.

    Người vận hành nền tảng qua nhờ một điều KHÁC: họ nắm một grant ở phạm vi
    SYSTEM. Điều đó cần thiết vì họ thường không phải thành viên của tenant mà
    họ đang xử lý (đình chỉ, xoá, hỗ trợ), và đòi vai tenant ở đây sẽ làm mọi
    thao tác vận hành trả 403.

    Grant ấy được đọc từ HAI nguồn, và cả hai đều là phát biểu tường minh về
    quyền chứ không phải suy luận từ sự vắng mặt:

        role_assignments (membership_id IS NULL)   nguồn v5, đã backfill
        users.is_admin                             cách nói cũ của cùng vai đó

    Nguồn thứ hai còn ở đây vì `AUTHZ_MODE=shadow`: hệ cũ vẫn là bên quyết
    định, và `is_admin` CHÍNH LÀ `platform_administrator` được viết bằng một
    cột. Nó đi cùng lúc với cột đó ở Phase D, không sớm hơn.

    Vì sao có câu hỏi THỨ BA (sửa 21/08/2026)
    ------------------------------------------
    Bản đầu chỉ hỏi hai câu: grant phạm vi SYSTEM, và vai ở SỔ CŨ
    (`tenant_members.role`). Câu thứ hai không đọc `role_assignments` chút nào
    — `tenant_members` là một VIEW trên `memberships` phơi ra `legacy_role AS
    role`, và cột ấy bị `ck_memberships_legacy_role_valid` giới hạn ở
    `admin | editor | NULL`.

    Hệ quả đo được: danh mục có 13 vai dựng sẵn; 2 vai phạm vi SYSTEM qua nhờ
    câu 1; trong 11 vai còn lại chỉ `tenant_administrator` và `tenant_editor`
    có bản sao ở sổ cũ. **Chín vai còn lại tự nó không đưa được ai qua cổng.**

    Chuyện chưa vỡ ra vì mười tài khoản đang dùng hệ thống đều nắm vai tenant
    CÓ bản sao — cổng đọc bản sao chứ không đọc vai thật. Nó sẽ vỡ ở tài khoản
    đầu tiên chỉ nắm vai v5: `community_member` (giữ `sample.create` và
    `upload.create`) không thể có bản sao nào ở sổ cũ, nên mọi lượt ghi của một
    thành viên cộng đồng sẽ trả 403. `project_contributor` — vai mà mô tả của
    chính nó nói là để "đóng góp và gán nhãn dữ liệu trong project" — cũng vậy.

    Câu thứ ba đọc `role_assignments` với `membership_id` KHÔNG NULL, nối
    `memberships` để một vai gắn vào tư cách thành viên đã gỡ không còn tính.
    Nó KHÔNG nới thêm gì cho người chưa được cấp gì: trạng thái "không grant
    nào cả" — kể cả thành viên được mời không kèm vai — vẫn bị từ chối, và
    `test_access_gate_scope_coverage.py` ghim cả hai chiều đó.

    Hỏng-thì-ĐÓNG: một lỗi khi tra cứu trả về `False`. Đây là cổng chặn, và một
    `except` trả `True` sẽ biến mọi sự cố cơ sở dữ liệu thành một lần mở quyền.
    """
    # `is_admin` được hỏi TRƯỚC, và thứ tự này là một lỗi đã mắc rồi sửa.
    #
    # Bản trước đòi có `user_id` trước đã, rồi mới xét quyền hệ thống. Nhưng vế
    # thứ nhất là điều kiện để TRA CỨU, không phải điều kiện để có quyền — và
    # 10 test dựng người vận hành bằng `{"id": None, "is_admin": True}` đã ăn
    # 403 vì đúng chuyện đó. Một tài khoản nắm quyền toàn nền tảng không mất nó
    # chỉ vì chỗ gọi không đọc được id.
    if user.get("is_admin"):
        return True

    user_id = user.get("id") or user.get("user_id")
    if not user_id:
        # Không có id thì không tra được grant nào. Hỏng-thì-đóng.
        return False

    try:
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import system_scope

        # System scope, cùng lý do như `vocabulary_registry.tenant_role`: câu
        # hỏi cố ý cắt ngang mọi tenant. Cả hai truy vấn là phép tra theo
        # user_id, `LIMIT 1`, trả về một hằng số — không liệt kê được gì.
        with system_scope("access gate: tai khoan nay co grant nao khong"):
            system_grant = _fetch_all(
                "SELECT 1 FROM role_assignments a JOIN roles r ON r.role_id = a.role_id "
                " WHERE a.user_id = %s AND a.membership_id IS NULL "
                "   AND a.revoked_at IS NULL AND r.is_active LIMIT 1",
                (str(user_id),),
            )
            if system_grant:
                return True

            # Grant v5 gắn với một tư cách thành viên — TENANT, WORKSPACE hoặc
            # PROJECT. Đây là câu hỏi mà cổng thiếu cho tới 21/08/2026, và nó
            # là câu duy nhất trả lời được cho chín vai không có bản sao ở sổ
            # cũ. Xem docstring bên trên.
            #
            # Nối `memberships` chứ không chỉ đọc `role_assignments`: một vai
            # gắn vào tư cách thành viên đã bị gỡ không còn là grant. Nối theo
            # CẢ `membership_id` và `user_id` — đúng hình khoá ngoại ghép
            # `fk_role_assignments_membership` — để một dòng gán trỏ vào
            # membership của người khác không đếm được cho người này.
            scoped_grant = _fetch_all(
                "SELECT 1 FROM role_assignments a "
                "  JOIN roles r ON r.role_id = a.role_id "
                "  JOIN memberships m ON m.membership_id = a.membership_id "
                "                    AND m.user_id = a.user_id "
                " WHERE a.user_id = %s AND a.membership_id IS NOT NULL "
                "   AND a.revoked_at IS NULL AND r.is_active "
                "   AND m.status = 'ACTIVE' AND m.left_at IS NULL LIMIT 1",
                (str(user_id),),
            )
            if scoped_grant:
                return True

            tenant_grant = _fetch_all(
                "SELECT 1 FROM tenant_members "
                " WHERE user_id = %s AND role IS NOT NULL "
                "   AND status = 'ACTIVE' AND removed_at IS NULL LIMIT 1",
                (str(user_id),),
            )
        return bool(tenant_grant)
    except Exception:
        logger.exception(
            "[ACCESS-GATE] khong tra duoc grant cho %s; tu choi theo huong dong",
            user_id,
        )
        return False


def _resolve_user(request: Request):
    """Ai đang gọi, hoặc None.

    Hai chi tiết ở đây đều là lỗi đã mắc phải rồi sửa, nên đáng ghi lại.

    **Bearer phải tự đọc.** `get_current_user_optional(request, credentials)`
    lấy cookie từ `request` nhưng lấy token Bearer từ tham số thứ hai — thứ mà
    FastAPI bơm vào qua hệ dependency. Middleware chạy ngoài hệ đó, nên truyền
    `None` khiến MỌI client dùng Authorization header bị 401 trong khi trình
    duyệt vẫn chạy bình thường. Triệu chứng chỉ xuất hiện với client API.

    **`dependency_overrides` phải được tôn trọng.** Middleware nằm ngoài hệ
    dependency nên không thấy chúng. Đó là điểm mở rộng chính thức của FastAPI
    và là cách 28 test giả lập đăng nhập; bỏ qua nó biến một cổng đúng thành
    một cổng không kiểm được. Tra tay ở đây là cái giá phải trả cho việc đặt
    cổng ở middleware — và đặt nó ở middleware là thứ khiến nó phủ cả những
    route khai báo thẳng trên `app`, ngoài mọi router.
    """
    from fastapi.security import HTTPAuthorizationCredentials

    from app.auth import get_current_user_optional
    from app.main import app

    resolver = app.dependency_overrides.get(
        get_current_user_optional, get_current_user_optional)

    credentials = None
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token.strip())

    try:
        if resolver is get_current_user_optional:
            return resolver(request, credentials)
        # Bản ghi đè trong test thường không nhận tham số nào.
        try:
            return resolver()
        except TypeError:
            return resolver(request, credentials)
    except Exception:
        # Một token hỏng là "chưa đăng nhập", không phải lỗi máy chủ.
        return None


def _unauthorised(detail: str, code: str, extra: Optional[dict] = None) -> JSONResponse:
    body = {"detail": detail, "code": code}
    if extra:
        body.update(extra)
    return JSONResponse(status_code=401, content=body)


async def access_gate(request: Request, call_next):
    """Chặn mọi request không thuộc một trong ba mức.

    Thứ tự kiểm quan trọng: OPTIONS đi trước tất cả, vì trình duyệt gửi preflight
    KHÔNG kèm cookie hay header xác thực. Chặn nó sẽ làm hỏng mọi lời gọi
    cross-origin mà không có dấu vết nào trong log ứng dụng.
    """
    if request.method == "OPTIONS":
        return await call_next(request)

    key = (request.method, canonical(request.url.path))

    if key in PUBLIC_ROUTES:
        return await call_next(request)

    user = _resolve_user(request)

    if user is not None:
        # Cổng thứ hai — xem khối chú thích ở `SELF_SERVICE_WRITE_PREFIXES`.
        #
        # Chỉ chạy cho phương thức ĐỔI TRẠNG THÁI và chỉ khi đường không thuộc
        # mặt phẳng tự phục vụ. Hai điều kiện đó giữ chi phí ở đúng chỗ: một
        # truy vấn điểm theo khoá chính, trên đường ghi, cho người không phải
        # quản trị viên nền tảng.
        path = canonical(request.url.path)
        if request.method not in _SAFE_METHODS and not _is_self_service_write(path):
            if not _has_any_tenant_grant(user):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            "Tài khoản của bạn là thành viên của tổ chức nhưng chưa "
                            "được cấp vai nào ở cấp tổ chức, nên chưa thực hiện được "
                            "thao tác này. Hãy đề nghị quản trị viên tổ chức cấp vai."
                        ),
                        "code": "no_tenant_role",
                    },
                )
        return await call_next(request)

    if key in TRIAL_OR_SESSION_ROUTES:
        from app.trial import consume_minute, describe, peek

        # `peek` báo cáo hạn ngạch chứ không phán quyền, nên với người chưa có
        # phiếu nó trả `allowed=True`. Ở cổng gác thì không phiếu = không vào;
        # `requiring_grant()` là phép biến đổi đó, đặt cạnh định nghĩa kiểu chứ
        # không dựng lại dataclass theo thứ tự tham số ở đây.
        grant = (consume_minute(request) if key in TRIAL_CONSUMING_ROUTES
                 else peek(request)).requiring_grant()
        if grant.allowed:
            response = await call_next(request)
            # Bộ đếm đi kèm MỌI phản hồi, không chỉ lúc hết: giao diện cần con
            # số để hiện đồng hồ, và lấy nó qua header thì không phải gọi thêm
            # một vòng nữa cho mỗi khung hình.
            response.headers["X-Trial-Minutes-Remaining"] = str(grant.minutes_remaining)
            response.headers["X-Trial-Minutes-Limit"] = str(grant.minutes_limit)
            return response
        return _unauthorised(describe(grant), "trial_exhausted", {
            "minutes_remaining": 0,
            "minutes_limit": grant.minutes_limit,
            "resets_at": grant.resets_at,
        })

    return _unauthorised("Not authenticated", "auth_required")
