"""Bề mặt công khai: cái gì mở, và làm sao biết nó không âm thầm rộng ra.

Trước 2026-08-07 mỗi endpoint TỰ CHỌN bật xác thực. Một lần quét toàn bộ tìm ra
tám chỗ bỏ sót — trong đó `/classes/collectors` trả về mười tên thật và
`POST /classes/register` cho khách vãng lai tạo lớp mới.

Test đáng giá nhất ở đây là `test_reachable_surface_matches_the_declaration`:
nó không kiểm một endpoint nào cụ thể, nó kiểm rằng **tập hợp** endpoint gọi
được khi chưa đăng nhập đúng bằng tập hợp đã khai báo. Một endpoint mới lọt vào
bề mặt công khai sẽ đỏ ở đây chứ không đỏ ở một bản kiểm bảo mật sau này.
"""

from __future__ import annotations

import pytest

from app.access_gate import (
    PUBLIC_ROUTES, TRIAL_OR_SESSION_ROUTES, canonical,
)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from conftest import LoopbackPeer
    from app.main import app

    return TestClient(LoopbackPeer(app))


# ---------------------------------------------------------------- canonical


class TestCanonical:
    """Đường có phiên bản và không phiên bản là CÙNG một endpoint.

    `main.py` mount mỗi router hai lần. Chuẩn hoá sai nghĩa là đóng bản có
    phiên bản mà để hở bản không phiên bản — hoặc ngược lại.
    """

    @pytest.mark.parametrize("raw,want", [
        ("/api/v1/classes/list", "/classes/list"),
        ("/classes/list", "/classes/list"),
        ("/api/v1/health/", "/health"),
        ("/health/", "/health"),
        ("/api/v1/health", "/health"),
        ("/", "/"),
        ("/api/v1", "/"),
        ("/api/v1/", "/"),
        # Không được cắt nhầm một đường chỉ TÌNH CỜ bắt đầu bằng chuỗi đó
        ("/api/v10/x", "/api/v10/x"),
    ])
    def test_normalises(self, raw, want):
        assert canonical(raw) == want


class TestTheDeclarationItself:
    def test_no_public_route_is_parameterised(self):
        """Middleware chạy TRƯỚC định tuyến nên chỉ thấy đường thật, không thấy
        template. Một mục chứa `{` sẽ không bao giờ khớp và endpoint đó âm thầm
        bị đóng — hỏng theo hướng an toàn, nhưng vẫn là hỏng."""
        for method, path in PUBLIC_ROUTES | TRIAL_OR_SESSION_ROUTES:
            assert "{" not in path, f"{method} {path} là template, không khớp được"

    def test_no_route_is_in_both_lists(self):
        """Một đường vừa công khai vừa cần phiếu là mâu thuẫn: nhánh công khai
        chạy trước nên phiếu không bao giờ được kiểm, và người đọc mã sẽ tin
        ngược lại."""
        assert not (PUBLIC_ROUTES & TRIAL_OR_SESSION_ROUTES)

    def test_every_declared_path_is_canonical(self):
        """Khai báo `/api/v1/x` sẽ không bao giờ khớp, vì so sánh diễn ra sau
        khi chuẩn hoá."""
        for method, path in PUBLIC_ROUTES | TRIAL_OR_SESSION_ROUTES:
            assert canonical(path) == path, f"{path} chưa chuẩn hoá"

    def test_no_write_method_is_public_except_session_bootstrap(self):
        """Khách vãng lai chỉ XEM. Ngoại lệ duy nhất là những đường phải mở để
        một người chưa có gì bắt đầu được: đăng nhập, đăng ký, xin phiếu."""
        allowed_writes = {
            "/auth/login", "/auth/register", "/auth/refresh", "/auth/logout",
            "/auth/forgot-password", "/auth/reset-password",
            "/auth/recover/start", "/auth/recover/verify", "/auth/recover/confirm",
            "/tenants/invitations/inspect", "/trial/start",
        }
        for method, path in PUBLIC_ROUTES:
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                assert path in allowed_writes, f"{method} {path} ghi mà công khai"


# ------------------------------------------------- bề mặt thật, đo bằng HTTP


def _probeable_routes(app):
    """Mọi (method, đường) gọi thử được — bỏ route có tham số."""
    seen = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or set()
        if "{" in path or not path.startswith("/"):
            continue
        for m in methods:
            if m in {"HEAD", "OPTIONS"}:
                continue
            seen.add((m, canonical(path)))
    return seen


class TestReachableSurface:
    def test_reachable_surface_matches_the_declaration(self, client):
        """Phép khẳng định trung tâm của file này.

        Gọi MỌI route không tham số mà không kèm chứng danh. Bất cứ thứ gì
        không trả 401 đều phải nằm trong một trong hai danh sách. So bằng phép
        bằng nhau chứ không phải bao hàm: một endpoint bị đóng nhầm cũng là lỗi,
        và nó lộ ra như một mục thừa trong danh sách.
        """
        from app.main import app

        declared = PUBLIC_ROUTES | TRIAL_OR_SESSION_ROUTES
        reachable = set()
        for method, path in sorted(_probeable_routes(app)):
            res = client.request(method, "/api/v1" + path if path != "/" else "/")
            if res.status_code != 401:
                reachable.add((method, path))

        unexpected = reachable - declared
        assert not unexpected, (
            f"gọi được mà KHÔNG khai báo: {sorted(unexpected)}. "
            f"Thêm vào access_gate nếu cố ý."
        )

    @pytest.mark.parametrize("method,path", [
        # Trả về mười tên thật của người đóng góp
        ("GET", "/api/v1/classes/collectors"),
        # Hồ sơ hoạt động gắn tên: ai thu, nhãn nào, bao nhiêu mẫu, lúc nào
        ("GET", "/api/v1/dataset/sessions"),
        # Lộ tên vai trò cơ sở dữ liệu và một cấu hình sai
        ("GET", "/api/v1/health/config"),
        ("GET", "/api/v1/health/deps"),
        # Tạo lớp mới, ẩn danh — hai đường khác nhau cùng làm một việc
        ("POST", "/api/v1/classes/register"),
        ("POST", "/api/v1/dataset/labels"),
        # Móc thử nghiệm sống trong production
        ("POST", "/api/v1/test/trigger-hardware-error"),
        ("POST", "/api/v1/tts/prewarm"),
    ])
    def test_the_eight_holes_are_closed(self, client, method, path):
        """Tám chỗ tìm được khi quét, mỗi chỗ một dòng.

        Liệt kê thẳng thay vì dựa vào test tập hợp ở trên: nếu ai đó nới danh
        sách khai báo, test kia sẽ xanh trở lại còn test này thì không.
        """
        res = client.request(method, path)
        assert res.status_code == 401, f"{method} {path} vẫn mở: {res.status_code}"

    @pytest.mark.parametrize("path", [
        "/api/v1/classes/list",
        "/api/v1/dataset/labels",
        "/api/v1/vocabulary/registry",
        "/api/v1/classes/community-stats",
    ])
    def test_the_library_stays_open(self, client, path):
        """Khách vãng lai vẫn phải xem được thư viện — đó là yêu cầu, không phải
        một sự nới lỏng."""
        assert client.get(path).status_code == 200

    def test_preflight_is_never_blocked(self, client):
        """Trình duyệt gửi OPTIONS KHÔNG kèm cookie. Chặn nó làm hỏng mọi lời
        gọi cross-origin, và triệu chứng là một lỗi mạng vô danh phía client —
        không có dòng nào trong log ứng dụng."""
        res = client.request("OPTIONS", "/api/v1/admin/users")
        assert res.status_code != 401

    def test_healthcheck_paths_stay_open(self, client):
        """Container tự gọi 127.0.0.1/health; Prometheus scrape /metrics. Đóng
        hai đường này làm 13 container báo unhealthy và giám sát chết — một sự
        cố vận hành trông hoàn toàn không giống một thay đổi bảo mật."""
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/ready").status_code == 200
        assert client.get("/metrics").status_code == 200
