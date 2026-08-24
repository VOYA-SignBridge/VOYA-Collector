"""Đăng ký không lời mời KHÔNG được rơi vào tenant gốc.

Lỗ hổng được vá ở đây, viết lại đầy đủ vì test chỉ có giá trị khi người đọc
biết nó canh cái gì:

Trước v4, `register` gọi `create_user(tenant_id=None)`, mà `None` nghĩa là
tenant bootstrap — tổ chức đang giữ toàn bộ 3.860 mẫu thật. `users.is_active`
mặc định TRUE, nên tài khoản hoạt động ngay. Cùng lúc `POST /classes/register`
không có cổng quyền nào ngoài "đã đăng nhập".

Ghép ba điều đó: bất kỳ ai đăng ký được đều trở thành thành viên hoạt động của
tổ chức giữ dữ liệu thật, và GHI được vào danh mục lớp của nó. RLS không cứu
được — nó cô lập giữa các tenant, còn người này đã ở trong đúng tenant đó.

Mỗi test dưới đây chốt một mắt xích. Chúng phải đỏ nếu ai đó hoàn tác bất kỳ
mắt nào — kể cả khi hai mắt còn lại vẫn đúng.

CẬP NHẬT 22/08/2026 — mắt xích MỘT được mở lại có chủ ý
--------------------------------------------------------
Tên tệp giờ chỉ đúng một nửa, và giữ nguyên tên là có lý do: lịch sử git phải
chỉ thẳng vào chỗ khẳng định bị đảo.

Đăng ký lại rơi vào tenant khởi tạo — nhưng tenant ấy giờ **là Cộng đồng**, nơi
mọi người được phép có mặt. Cách vá của v4 (mỗi lượt đăng ký một tổ chức riêng)
bị bỏ vì nó đẻ ra một tenant rỗng kèm bản sao danh mục từ vựng cho mỗi người
thử nền tảng.

Lỗ hổng KHÔNG mở lại, vì thứ bịt nó đã đổi: không còn là sự tách biệt tenant mà
là TẬP QUYỀN. `community_member` mang đọc + `sample.create` + `upload.create`,
và KHÔNG mang `class.create`; route `POST /classes/register` gác bằng
`require_tenant_editor`. Hai thứ độc lập, và
`test_thanh_vien_cong_dong_KHONG_tao_duoc_lop` canh cả hai.

Hai bài về gói/chủ/hậu tố ngẫu nhiên KHÔNG bị xoá — chúng DỜI sang đường tự lập
tổ chức, nơi hành vi ấy thật sự sống bây giờ.
"""

from __future__ import annotations

import uuid

import pytest

from app.storage import metadata_db as db
from app.tenancy import DEFAULT_TENANT_ID


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


PW = "@Minh123456"


def _unique(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


@pytest.fixture
def anon_client():
    """Client không đăng nhập, mỗi lượt gọi mang một IP mới.

    IP mới cho mỗi request là bắt buộc chứ không phải cẩn thận thừa: bộ đếm
    rate-limit sống qua các lượt chạy suite, và một tệp dùng chung 127.0.0.1 sẽ
    bắt đầu trả 429 ở lượt chạy thứ N. Xem [[testing-infra]].
    """
    from fastapi.testclient import TestClient

    from conftest import LoopbackPeer, fresh_client_ip
    from app.main import app

    inner = TestClient(LoopbackPeer(app))

    class _PerRequestIp:
        def post(self, url, **kwargs):
            headers = {**kwargs.pop("headers", {}),
                       "X-Forwarded-For": fresh_client_ip()}
            return inner.post(url, headers=headers, **kwargs)

    return _PerRequestIp()


def _signed_in_client(*, is_admin: bool):
    from fastapi.testclient import TestClient

    from conftest import LoopbackPeer, fresh_client_ip
    from app import auth
    from app.main import app

    name = _unique("sgn")
    user = auth.create_user(
        username=name, email=f"{name}@example.com", password=PW, is_admin=is_admin
    )
    client = TestClient(LoopbackPeer(app))
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": name, "password": PW},
        headers={"X-Forwarded-For": fresh_client_ip()},
    )
    assert response.status_code == 200, response.text
    return client, user


def _csrf(client):
    from conftest import fresh_client_ip

    return {
        "X-CSRF-Token": client.cookies.get("voya_csrf", ""),
        "X-Forwarded-For": fresh_client_ip(),
    }


def _drop_account(username: str) -> None:
    """Uỷ cho bản dùng chung ở conftest — xem `purge_registered_account`."""
    from conftest import purge_registered_account

    purge_registered_account(username)


@pytest.fixture
def user_client():
    client, user = _signed_in_client(is_admin=False)
    yield client, user
    client.cookies.clear()
    _drop_account(user["username"])


@pytest.fixture
def admin_client():
    client, user = _signed_in_client(is_admin=True)
    yield client, user
    client.cookies.clear()
    _drop_account(user["username"])


@pytest.fixture
def registered_class():
    """Thu `class_uid` mà một test đăng ký, dọn ở cuối KỂ CẢ khi test đỏ.

    Phải dọn HAI nơi, và cái thứ hai là cái đã bị bỏ sót hai lần:

    **Cơ sở dữ liệu.** Bản trước xoá bằng một câu `_execute` viết ở CUỐI thân
    test, sau các phép khẳng định — một `assert` đỏ nhảy ra trước khi tới đó.
    Kết quả: `lop-thu-70eb62` rò vào `signdb` sản xuất, chiếm `class_idx 64`.

    **`dataset/labels.csv`.** `POST /classes/register` ghi vào cả bảng lẫn tệp.
    Chạy suite trên bản sao `signdb_test` che được đường ghi cơ sở dữ liệu
    nhưng **không che được đường ghi tệp** — `labels.csv` là một tệp dùng chung
    qua mount. Kết quả: `lop-thu-488e5d` nằm trong CSV thật mà không có ở cơ sở
    dữ liệu nào. Xem [[test-writes-to-real-csv]].

    Không dùng `catalog_sync.sync_delete_class`: nó là đường đúng cho ứng dụng
    nhưng còn đồng bộ sang Google Drive, tức là một fixture dọn dẹp sẽ gọi ra
    mạng và đỏ khi mất kết nối.
    """
    created: list[str] = []
    yield created

    from app.tenant_context import system_scope

    with system_scope("test cleanup: gỡ lớp vừa đăng ký"):
        for class_uid in reversed(created):
            try:
                db._execute("DELETE FROM classes WHERE class_uid = %s", (class_uid,))
            except Exception:
                # Mỗi lớp một `try` riêng: một câu hỏng không được chặn các câu
                # sau, nếu không thì lỗi ở lớp đầu để lại toàn bộ phần còn lại.
                pass
            try:
                _drop_class_from_labels_csv(class_uid)
            except Exception:
                pass


def _drop_class_from_labels_csv(class_uid: str) -> None:
    """Gỡ đúng một dòng khỏi `dataset/labels.csv`, giữ nguyên phần còn lại.

    Đọc-lọc-ghi lại toàn tệp thay vì sửa tại chỗ: tệp có cỡ 64 dòng, và một lượt
    ghi lại trọn vẹn không để lại trạng thái nửa vời nếu tiến trình chết giữa
    chừng.
    """
    import csv

    from app.dataset_manager import MASTER_LABELS

    if not MASTER_LABELS.exists():
        return
    with open(MASTER_LABELS, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or []
        rows = [r for r in reader if r.get("class_uid") != class_uid]
    if not fields:
        return
    with open(MASTER_LABELS, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def registered_accounts():
    """Thu tên tài khoản mà một test đăng ký, dọn hết ở cuối kể cả khi test đỏ.

    Chỉ giữ TÊN, không giữ id: `purge_registered_account` tự tra id và tự tìm
    tenant mà lượt đăng ký đó tạo ra. Giữ cả hai ở đây là chép lại một nửa
    logic dọn vào fixture, đúng thứ vừa được gom về một chỗ.
    """
    created: list[str] = []
    yield created

    from conftest import purge_registered_account

    for username in reversed(created):
        purge_registered_account(username)


def _register(anon_client, *, username: str, email: str, org: str | None = None):
    """Đăng ký, tự kèm số hiệu bản điều khoản ĐANG hiệu lực nếu có công bố.

    Đọc bản hiện hành thay vì viết cứng "1.0": bộ test này chạy trên bản sao
    của cơ sở dữ liệu thật, nơi văn bản pháp lý đã được công bố với số hiệu
    thật. Viết cứng sẽ cho ra 409 `stale_version` và test đỏ vì một lý do
    không liên quan gì tới thứ nó đang kiểm.
    """
    from app import legal

    body = {"username": username, "email": email, "password": PW}
    for kind in ("terms", "privacy"):
        current = legal.current_document(kind)
        if current:
            body[f"accepted_{kind}_version"] = current["version"]
    if org is not None:
        body["organization_name"] = org
    return anon_client.post("/api/v1/auth/register", json=body)


class TestSignupNeverLandsInTheBootstrapTenant:
    def test_dang_ky_vao_cong_dong_va_KHONG_lap_to_chuc(
        self, anon_client, registered_accounts
    ):
        """Mắt xích một, viết lại ở v6 — và mắt xích ĐỔI chứ lỗ hổng thì không.

        v4 vá lỗ bằng cách TÁCH tenant: mỗi lượt đăng ký sinh một tổ chức riêng.
        v6 bỏ cách ấy, vì nó đẻ ra một tenant rỗng kèm bản sao danh mục từ vựng
        cho mỗi người thử nền tảng, và vì tenant khởi tạo giờ CHÍNH LÀ Cộng
        đồng — nơi mọi người được phép có mặt.

        Cái bịt lỗ bây giờ là TẬP QUYỀN, không phải sự tách biệt: xem
        `test_thanh_vien_cong_dong_KHONG_tao_duoc_lop` bên dưới. Bài này chỉ
        chốt vế đầu — vào đúng chỗ, và không đẻ ra tổ chức nào.
        """
        from app.storage.authz_schema import COMMUNITY_TENANT_ID
        from app.tenant_context import system_scope

        with system_scope("test: dem to chuc truoc"):
            truoc = db._fetch_all("SELECT count(*) AS n FROM tenants")[0]["n"]

        username, email = _unique("selfserve"), f"{_unique('selfserve')}@example.com"
        response = _register(anon_client, username=username, email=email,
                             org="Truong Thu Nghiem")
        assert response.status_code == 201, response.text
        body = response.json()
        registered_accounts.append(username)

        assert body.get("tenant_id") == COMMUNITY_TENANT_ID

        with system_scope("test: dem to chuc sau"):
            sau = db._fetch_all("SELECT count(*) AS n FROM tenants")[0]["n"]
        assert sau == truoc, "dang ky van con lap to chuc"

    def test_thanh_vien_cong_dong_KHONG_tao_duoc_lop(self, anon_client,
                                                     registered_accounts):
        """Mắt xích BA, và giờ nó gánh phần mà sự tách biệt tenant từng gánh.

        Chuỗi lỗ hổng v3 gồm ba mắt: rơi vào tenant gốc + hoạt động ngay +
        `POST /classes/register` không có cổng quyền nào ngoài "đã đăng nhập".
        v6 mở lại mắt thứ nhất một cách CÓ CHỦ Ý, nên mắt thứ ba phải giữ.

        Nó giữ được vì hai thứ độc lập: route gác bằng `require_tenant_editor`,
        và `community_member` không mang `class.create`. Bài này đỏ nếu ai đó
        nới một trong hai.
        """
        username, email = _unique("comm"), f"{_unique('comm')}@example.com"
        res = _register(anon_client, username=username, email=email, org="")
        assert res.status_code == 201, res.text
        registered_accounts.append(username)

        from fastapi.testclient import TestClient

        from conftest import LoopbackPeer, fresh_client_ip
        from app.main import app

        client = TestClient(LoopbackPeer(app))
        dn = client.post("/api/v1/auth/login",
                         json={"identifier": username, "password": PW},
                         headers={"X-Forwarded-For": fresh_client_ip()})
        assert dn.status_code == 200, dn.text

        tao = client.post(
            "/api/v1/classes/register",
            json={"label_original": "thu tao lop", "language": "vn",
                  "dialect": "common"},
            headers=_csrf(client))
        client.cookies.clear()

        assert tao.status_code == 403, (
            f"thanh vien cong dong tao duoc lop (ma {tao.status_code}) — "
            f"mat xich ba da mo")

    def test_to_chuc_TU_LAP_co_goi_co_chu_va_nguoi_lap_lam_admin(self):
        """Ba bất biến của một tổ chức tự lập — DỜI CHỖ, không biến mất.

        Chúng từng được kiểm ở đường ĐĂNG KÝ, vì hồi ấy đăng ký tự lập tổ chức.
        Từ v6 việc lập tổ chức tách ra thành một hành động CÓ CHỦ ĐÍCH sau khi
        đăng nhập, nên bài kiểm đi theo hành vi chứ không ở lại chỗ cũ.

        Ba thứ đi cùng nhau: một tổ chức không gói đi qua mọi cổng hạn mức mà
        không bị hỏi; không admin thì không ai mời được ai; không chủ thì không
        biết hoá đơn gửi cho ai.
        """
        from conftest import purge_tenant
        from app import auth, tenant_admin
        from app.tenant_context import system_scope

        name = _unique("owner")
        user = auth.create_user(username=name, email=f"{name}@example.com",
                                password=PW)
        t = None
        try:
            t = tenant_admin.create_self_serve_tenant(
                str(user["id"]), display_name="Co So B")
            with system_scope("test: soi to chuc tu lap"):
                row = db._fetch_all(
                    "SELECT plan_code, owner_user_id, is_self_serve, billing_status "
                    "  FROM tenants WHERE tenant_id = %s", (t["tenant_id"],))[0]
                vai = db._fetch_all(
                    "SELECT role FROM tenant_members "
                    " WHERE tenant_id = %s AND user_id = %s",
                    (t["tenant_id"], str(user["id"])))
                dk = db._fetch_all(
                    "SELECT plan_code FROM tenant_subscriptions "
                    " WHERE tenant_id = %s AND ended_at IS NULL", (t["tenant_id"],))

            assert row["plan_code"] == "free"
            assert str(row["owner_user_id"]) == str(user["id"])
            assert row["is_self_serve"] is True
            # `free` là gói VĨNH VIỄN, không phải bản dùng thử: 'trialing' sẽ
            # hứa một cái hạn không bao giờ tới, và bảng "sắp hết hạn dùng thử"
            # liệt kê mọi người dùng miễn phí mãi mãi.
            assert row["billing_status"] == "active"
            assert vai and vai[0]["role"] == "admin"
            assert dk and dk[0]["plan_code"] == "free"
        finally:
            if t:
                purge_tenant(t["tenant_id"])
            _drop_account(name)

    def test_ma_to_chuc_KHONG_lo_ai_da_lap_truoc(self):
        """Hai tổ chức TRÙNG TÊN phải ra hai mã không đoán được.

        Một bộ đếm (`truong-b`, `truong-b-2`) biến ô tên thành máy dò: thử một
        cái tên và xem hậu tố trả về là biết đã có bao nhiêu tổ chức trùng tên
        trên nền tảng.

        Dời từ đường đăng ký sang đường tự lập, cùng lý do như bài trên.
        """
        from conftest import purge_tenant
        from app import auth, tenant_admin

        ten_tk, tao = [], []
        try:
            for _ in range(2):
                n = _unique("dup")
                u = auth.create_user(username=n, email=f"{n}@example.com",
                                     password=PW)
                ten_tk.append(n)
                tao.append(tenant_admin.create_self_serve_tenant(
                    str(u["id"]), display_name="Truong Trung Ten")["tenant_id"])

            assert tao[0] != tao[1], "hai to chuc trung ten ra cung mot ma"
            assert not tao[1].endswith("-2"), (
                "hau to la mot BO DEM — o ten tro thanh may do so to chuc "
                "trung ten da co tren nen tang")
        finally:
            for tid in tao:
                purge_tenant(tid)
            for n in ten_tk:
                _drop_account(n)

    def test_signup_is_refused_outright_when_self_serve_is_off(
        self, anon_client, monkeypatch, registered_accounts
    ):
        """Tắt tự phục vụ phải TỪ CHỐI, không được rơi về hành vi cũ.

        Đây là nhánh dễ bị làm sai nhất: một bản vá "an toàn" hay viết
        `if not self_serve: tenant = DEFAULT` — tức là dựng lại nguyên lỗ hổng
        và gọi nó là dự phòng.
        """
        from app.config import settings

        monkeypatch.setattr(settings, "self_serve_signup", False)
        username = _unique("closed")
        response = _register(anon_client, username=username, email=f"{username}@example.com")

        assert response.status_code == 403, response.text

        from app.tenant_context import system_scope

        with system_scope("test: prove the refused signup created nothing"):
            rows = db._fetch_all(
                "SELECT id FROM users WHERE username = %s", (username,)
            )
        assert rows == [], "đăng ký bị từ chối vẫn để lại tài khoản"


class TestCatalogWritesNeedMoreThanASession:
    def test_a_plain_contributor_cannot_add_a_class(self, user_client):
        """Mắt xích hai: `POST /classes/register` không còn mở cho mọi tài khoản.

        Người đóng góp mẫu là vai trò thấp nhất có phiên đăng nhập. Trước v4 vai
        trò đó ghi được vào danh mục dùng chung của cả tổ chức.
        """
        client, _ = user_client
        response = client.post(
            "/api/v1/classes/register",
            json={"label": "thu nghiem quyen", "language": "vn", "dialect": "common"},
            headers=_csrf(client),
        )
        assert response.status_code == 403, response.text

    def test_an_admin_still_can(self, admin_client, registered_class):
        """Phản chứng. Không có nó, test trên vẫn xanh khi endpoint hỏng hẳn."""
        client, _ = admin_client
        label = f"lop thu {uuid.uuid4().hex[:6]}"
        response = client.post(
            "/api/v1/classes/register",
            json={"label": label, "language": "vn", "dialect": "common"},
            headers=_csrf(client),
        )
        assert response.status_code == 200, response.text
        registered_class.append(response.json()["class_uid"])
