"""Điều khoản: có phiên bản, có bằng chứng, và cưỡng chế bật bằng cách công bố.

Ba tính chất được kiểm ở đây, và cái thứ ba là cái dễ tin mà không kiểm nhất:

  * chấp thuận ghi lại BẢN NÀO, không phải một cờ boolean
  * sửa nội dung mà giữ số hiệu phiên bản bị TỪ CHỐI — nếu không, mọi chữ ký đã
    thu trỏ tới một bản văn không còn là bản người ta đọc
  * deployment CHƯA công bố văn bản thì đăng ký vẫn chạy, và điều đó lộ ra ở
    `verify_deployment` chứ không lộ ra âm thầm
"""

from __future__ import annotations

import uuid

import pytest

from app import legal
from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


#: Cột được chụp lại. Viết tay chứ không `SELECT *`: thứ tự cột của `*` là thứ
#: tự trong catalog, và một cột thêm sau sẽ lặng lẽ làm lệch câu INSERT phục hồi.
_DOC_COLUMNS = (
    "doc_id", "kind", "version", "effective_from", "content_hash", "url",
    "title", "requires_reconsent", "body", "body_format", "language",
    "change_summary", "published_at", "published_by",
)
_CONSENT_COLUMNS = (
    "consent_id", "user_id", "kind", "version", "accepted_at", "ip_hash",
    "user_agent", "withdrawn_at", "source", "note", "recorded_by",
)


def _snapshot(table: str, columns: tuple) -> list:
    with system_scope("test: chụp lại bảng nền tảng trước khi dọn"):
        return [tuple(r[c] for c in columns)
                for r in db._fetch_all(f"SELECT {', '.join(columns)} FROM {table}")]


def _restore(table: str, columns: tuple, rows: list) -> None:
    if not rows:
        return
    placeholders = ", ".join(["%s"] * len(columns))
    with system_scope("test: trả bảng nền tảng về đúng trạng thái trước suite"):
        for row in rows:
            db._execute(
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                row,
            )


@pytest.fixture(scope="module", autouse=True)
def _preserve_published_documents(_ensure_schema):
    """Trả lại những văn bản ĐÃ CÔNG BỐ mà tệp test này phải dọn đi.

    Vì sao cần: `legal_documents` áp cho cả nền tảng và KHÔNG có RLS, nên
    `DELETE FROM legal_documents` ở fixture bên dưới xoá sạch bảng thật chứ
    không phải một phần dữ liệu của test. Bộ test chạy trên bản sao của cơ sở
    dữ liệu sản xuất — nơi các bản điều khoản thật đang nằm — nên một lượt chạy
    suite từng đủ để bản sao khác production ở đúng cái bảng mà mọi chấp thuận
    trỏ tới.

    Sổ dấu vết ở conftest không bắt được chuyện này: nó theo dõi những hàng
    được TẠO ra và dọn chúng, chứ không phục hồi những hàng bị XOÁ đi.

    Thứ tự có ý nghĩa ở cả hai chiều. Xoá: chấp thuận trước, văn bản sau — khoá
    ngoại `(kind, version)` là `ON DELETE RESTRICT`. Phục hồi: ngược lại.
    """
    documents = _snapshot("legal_documents", _DOC_COLUMNS)
    consents = _snapshot("user_consents", _CONSENT_COLUMNS)
    yield
    _restore("legal_documents", _DOC_COLUMNS, documents)
    _restore("user_consents", _CONSENT_COLUMNS, consents)


@pytest.fixture(autouse=True)
def _clean_documents(_preserve_published_documents):
    """Mỗi test bắt đầu KHÔNG có văn bản nào.

    Bảng `legal_documents` áp cho cả nền tảng, nên một bản còn sót từ test
    trước sẽ bật cưỡng chế cho test sau và làm nó đỏ vì lý do không liên quan.
    """
    def _wipe():
        with system_scope("test cleanup"):
            db._execute("DELETE FROM user_consents")
            db._execute("DELETE FROM legal_documents")

    _wipe()
    yield
    _wipe()


@pytest.fixture
def anon_client():
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


def _publish(kind="terms", version="2026-08-07", body="Nội dung điều khoản."):
    return legal.register_document(
        kind, version, url=f"/legal/{kind}", body=body, title=kind.title())


@pytest.fixture
def account():
    from app.auth import create_user

    name = f"lgl{uuid.uuid4().hex[:9]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery")
    yield user
    with system_scope("test cleanup"):
        db._execute("DELETE FROM user_consents WHERE user_id = %s", (user["id"],))
        db._execute("DELETE FROM tenant_members WHERE user_id = %s", (user["id"],))
        db._execute("DELETE FROM users WHERE id = %s", (user["id"],))


class TestDocumentVersioning:
    def test_republishing_identical_content_is_idempotent(self):
        """Chạy lại lệnh công bố với đúng file cũ không được coi là lỗi — người
        vận hành chạy lại script triển khai là chuyện bình thường."""
        first = _publish()
        again = _publish()
        assert first["version"] == again["version"]

    def test_changing_content_under_the_same_version_is_refused(self):
        """Tính chất trung tâm.

        Mọi chấp thuận đã thu trỏ tới `(kind, version)`. Đổi nội dung dưới chân
        chúng biến bằng chứng thành lời khẳng định suông: bản ghi nói người ta
        đồng ý bản 2026-08-07, nhưng bản 2026-08-07 giờ nói điều khác.
        """
        _publish(body="Bản gốc.")
        with pytest.raises(legal.ConsentError) as exc:
            _publish(body="Đã bị sửa lén.")
        assert exc.value.code == "version_content_mismatch"

    def test_content_hash_is_recorded(self):
        """Số hiệu phiên bản là thứ con người đặt; hash là thứ máy kiểm. Không
        có hash thì không phát hiện được việc sửa file mà quên tăng số."""
        doc = _publish(body="Nội dung cụ thể.")
        assert doc["content_hash"] == legal.content_hash("Nội dung cụ thể.")

    def test_an_unknown_kind_is_refused(self):
        with pytest.raises(legal.ConsentError):
            legal.register_document("khong-ton-tai", "1", url="/x", body="y")


class TestRecordingConsent:
    def test_a_consent_names_the_version(self, account):
        _publish(version="1.0")
        legal.record_consent(account["id"], "terms", "1.0")
        with system_scope("test read"):
            rows = db._fetch_all(
                "SELECT version FROM user_consents WHERE user_id = %s",
                (account["id"],))
        assert rows[0]["version"] == "1.0"

    def test_a_stale_version_is_refused(self, account):
        """Một biểu mẫu cũ còn mở trong tab sẽ gửi số hiệu cũ. Chấp nhận nó là
        thu chữ ký cho một bản văn đã bị thay thế."""
        _publish(version="1.0")
        with pytest.raises(legal.ConsentError) as exc:
            legal.record_consent(account["id"], "terms", "0.9")
        assert exc.value.code == "stale_version"

    def test_consenting_to_a_new_version_supersedes_the_old_one(self, account):
        """Chỉ mục duy nhất bộ phận cho phép ĐÚNG MỘT chấp thuận còn hiệu lực
        cho mỗi (người, loại). Bản cũ phải được đánh dấu rút, không phải xoá —
        lịch sử ai đồng ý bản nào lúc nào chính là thứ cần giữ."""
        _publish(version="1.0")
        legal.record_consent(account["id"], "terms", "1.0")
        _publish(version="2.0", body="Bản hai.")
        legal.record_consent(account["id"], "terms", "2.0")

        with system_scope("test read"):
            rows = db._fetch_all(
                "SELECT version, withdrawn_at FROM user_consents "
                "WHERE user_id = %s ORDER BY accepted_at", (account["id"],))
        assert len(rows) == 2
        assert rows[0]["withdrawn_at"] is not None   # bản cũ đã rút
        assert rows[1]["withdrawn_at"] is None       # bản mới còn hiệu lực

    def test_has_consent_is_false_before_and_true_after(self, account):
        _publish()
        assert legal.has_consent(account["id"], "terms") is False
        legal.record_consent(account["id"], "terms", "2026-08-07")
        assert legal.has_consent(account["id"], "terms") is True

    def test_reconsent_invalidates_an_older_acceptance(self, account):
        """`requires_reconsent` là ranh giới giữa "sửa lỗi chính tả" và "đổi
        phạm vi xử lý dữ liệu". Chỉ cái sau mới được đá người dùng ra màn hình
        đồng ý."""
        _publish(version="1.0")
        legal.record_consent(account["id"], "terms", "1.0")

        legal.register_document("terms", "2.0", url="/legal/terms",
                                body="Phạm vi mới.", requires_reconsent=True)
        assert legal.has_consent(account["id"], "terms") is False

    def test_a_cosmetic_new_version_keeps_the_old_acceptance(self, account):
        _publish(version="1.0")
        legal.record_consent(account["id"], "terms", "1.0")
        legal.register_document("terms", "1.1", url="/legal/terms",
                                body="Sửa chính tả.", requires_reconsent=False)
        assert legal.has_consent(account["id"], "terms") is True


class TestRegistrationEnforcement:
    def test_registration_works_when_nothing_is_published(self, anon_client):
        """Công bố CHÍNH LÀ bật cưỡng chế.

        Một bản triển khai chưa công bố điều khoản thì không có gì để đồng ý,
        và chặn đăng ký ở đó biến "chưa dùng tính năng" thành một sự cố.
        """
        name = f"t{uuid.uuid4().hex[:10]}"
        res = anon_client.post("/api/v1/auth/register", json={
            "username": name, "email": f"{name}@example.test",
            "password": "correct horse battery",
        })
        assert res.status_code == 201, res.text
        _purge(name)

    def test_registration_is_refused_without_consent_once_published(self, anon_client):
        _publish("terms", "1.0")
        _publish("privacy", "1.0", body="Quyền riêng tư.")
        name = f"t{uuid.uuid4().hex[:10]}"
        res = anon_client.post("/api/v1/auth/register", json={
            "username": name, "email": f"{name}@example.test",
            "password": "correct horse battery",
        })
        assert res.status_code == 400
        assert res.json()["detail"]["code"] == "consent_required"
        # Câu trả lời phải nói RÕ bản nào và đọc ở đâu, nếu không giao diện
        # không dựng được màn hình đồng ý.
        assert res.json()["detail"]["version"] == "1.0"
        assert res.json()["detail"]["url"]

    def test_registration_succeeds_with_both_versions(self, anon_client):
        _publish("terms", "1.0")
        _publish("privacy", "1.0", body="Quyền riêng tư.")
        name = f"t{uuid.uuid4().hex[:10]}"
        res = anon_client.post("/api/v1/auth/register", json={
            "username": name, "email": f"{name}@example.test",
            "password": "correct horse battery",
            "accepted_terms_version": "1.0",
            "accepted_privacy_version": "1.0",
        })
        assert res.status_code == 201, res.text

        with system_scope("test read"):
            rows = db._fetch_all(
                "SELECT kind, version, ip_hash FROM user_consents "
                "WHERE user_id = %s ORDER BY kind", (res.json()["id"],))
        assert [r["kind"] for r in rows] == ["privacy", "terms"]
        # Bằng chứng đi kèm: BĂM địa chỉ, không phải địa chỉ.
        assert all(r["ip_hash"] and len(r["ip_hash"]) == 64 for r in rows)
        _purge(name)

    def test_a_stale_version_from_an_open_tab_is_refused(self, anon_client):
        _publish("terms", "2.0")
        _publish("privacy", "2.0", body="Quyền riêng tư.")
        name = f"t{uuid.uuid4().hex[:10]}"
        res = anon_client.post("/api/v1/auth/register", json={
            "username": name, "email": f"{name}@example.test",
            "password": "correct horse battery",
            "accepted_terms_version": "1.0",
            "accepted_privacy_version": "2.0",
        })
        assert res.status_code == 409
        assert res.json()["detail"]["code"] == "stale_version"

    def test_no_account_is_created_when_consent_is_missing(self, anon_client):
        """Kiểm TRƯỚC khi tạo tài khoản. Tạo trước rồi mới từ chối để lại một
        tài khoản thật mà người dùng không biết mình có — và lần thử lại sẽ đụng
        chính username họ vừa chiếm."""
        _publish("terms", "1.0")
        _publish("privacy", "1.0", body="Quyền riêng tư.")
        name = f"t{uuid.uuid4().hex[:10]}"
        anon_client.post("/api/v1/auth/register", json={
            "username": name, "email": f"{name}@example.test",
            "password": "correct horse battery",
        })
        with system_scope("test read"):
            rows = db._fetch_all(
                "SELECT id FROM users WHERE username = %s", (name,))
        assert rows == []


class TestRegistrationSendsTheVerificationCode:
    """Không có bước này thì `REQUIRE_EMAIL_VERIFICATION` là một cái bẫy.

    Người dùng đăng ký, đăng nhập, bị từ chối vì chưa xác minh — và trong hộp
    thư không có gì để xác minh bằng.
    """

    def test_a_code_is_issued_at_registration(self, anon_client, monkeypatch):
        sent = []
        import app.routers.auth as auth_router

        monkeypatch.setattr(
            "app.email_service.send_verification_code_email",
            lambda to, code, purpose: sent.append((to, purpose)))
        monkeypatch.setattr(auth_router.settings, "otp_pepper",
                            "pepper-for-tests-at-least-32-chars", raising=False)

        name = f"t{uuid.uuid4().hex[:10]}"
        res = anon_client.post("/api/v1/auth/register", json={
            "username": name, "email": f"{name}@example.test",
            "password": "correct horse battery",
        })
        assert res.status_code == 201, res.text

        with system_scope("test read"):
            rows = db._fetch_all(
                "SELECT purpose FROM verification_codes WHERE user_id = %s",
                (res.json()["id"],))
        assert [r["purpose"] for r in rows] == ["verify_email"]
        _purge(name)

    def test_a_broken_mailer_does_not_fail_the_registration(
        self, anon_client, monkeypatch
    ):
        """Tài khoản đã tồn tại và giao dịch đã xong. Ném lỗi ở đây trả 500 cho
        một request đã thành công, và người dùng sẽ thử lại rồi đụng chính
        username họ vừa chiếm."""
        def _explode(*_a, **_k):
            raise RuntimeError("SMTP chết")

        monkeypatch.setattr("app.otp.issue", _explode)

        name = f"t{uuid.uuid4().hex[:10]}"
        res = anon_client.post("/api/v1/auth/register", json={
            "username": name, "email": f"{name}@example.test",
            "password": "correct horse battery",
        })
        assert res.status_code == 201, res.text
        _purge(name)

    def test_the_code_never_reaches_a_log(self, anon_client, monkeypatch, caplog):
        """Thông điệp của một lỗi SMTP có thể mang theo cả nội dung thư — và nội
        dung thư ở đây chính là mã. Nên nhánh lỗi chỉ ghi TÊN LOẠI ngoại lệ."""
        import logging

        def _explode_with_the_code(*_a, **_k):
            raise RuntimeError("gửi thất bại, thư chứa: 424242")

        monkeypatch.setattr("app.otp.issue", _explode_with_the_code)

        name = f"t{uuid.uuid4().hex[:10]}"
        with caplog.at_level(logging.DEBUG):
            anon_client.post("/api/v1/auth/register", json={
                "username": name, "email": f"{name}@example.test",
                "password": "correct horse battery",
            })
        assert "424242" not in caplog.text
        _purge(name)


class TestPublicReading:
    """Văn bản phải đọc được TRƯỚC khi có tài khoản — nếu không, ô tích đồng ý
    không có gì để mở."""

    def test_every_legal_kind_is_publicly_readable(self):
        """Cổng khớp ĐƯỜNG chứ không khớp template `/legal/{kind}`, nên mỗi giá
        trị trong `legal.KINDS` phải có một dòng riêng trong PUBLIC_ROUTES. Thêm
        một `kind` mà quên dòng đó sẽ khiến nó 401 — hỏng an toàn, nhưng lặng
        lẽ, nên phép khẳng định này tồn tại."""
        from app.access_gate import PUBLIC_ROUTES

        for kind in legal.KINDS:
            assert ("GET", f"/legal/{kind}") in PUBLIC_ROUTES, kind

    def test_reading_an_unpublished_document_is_404_not_401(self, anon_client):
        from fastapi.testclient import TestClient
        from conftest import LoopbackPeer
        from app.main import app

        res = TestClient(LoopbackPeer(app)).get("/api/v1/legal/terms")
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "not_published"

    def test_a_published_document_returns_its_version_and_hash(self):
        from fastapi.testclient import TestClient
        from conftest import LoopbackPeer
        from app.main import app

        _publish("terms", "3.0", body="Bản ba.")
        res = TestClient(LoopbackPeer(app)).get("/api/v1/legal/terms")
        assert res.status_code == 200
        body = res.json()
        assert body["version"] == "3.0"
        # Hash cho phép giao diện chứng minh nó hiển thị đúng bản đã ghi nhận.
        assert body["content_hash"] == legal.content_hash("Bản ba.")

    def test_an_unknown_kind_is_404_with_the_valid_list(self):
        from fastapi.testclient import TestClient
        from conftest import LoopbackPeer
        from app.main import app

        # Không nằm trong PUBLIC_ROUTES nên cổng chặn trước — 401, không phải
        # 404. Đó là hành vi đúng: không tiết lộ đường nào có thật.
        res = TestClient(LoopbackPeer(app)).get("/api/v1/legal/khong-ton-tai")
        assert res.status_code == 401


class TestDeploymentCheckCatchesTheGap:
    def test_missing_documents_are_reported(self):
        """Cưỡng chế bật bằng cách công bố, nên "quên công bố" trông giống hệt
        "chạy bình thường". Đây là chỗ duy nhất nó lộ ra."""
        assert set(legal.missing_for_registration()) == {"terms", "privacy"}
        _publish("terms", "1.0")
        assert legal.missing_for_registration() == ["privacy"]
        _publish("privacy", "1.0", body="Quyền riêng tư.")
        assert legal.missing_for_registration() == []


class TestMyConsentsEndpoint:
    """Hợp đồng mà màn hình "Chấp thuận của tôi" đứng lên.

    Trang đó không có nguồn nào khác để biết bạn đã ký gì. Mỗi trường thiếu ở
    đây là một câu sai trên màn hình, chứ không phải một chi tiết thẩm mỹ — nên
    từng trường được ghim riêng.
    """

    @pytest.fixture
    def signed_in(self, account):
        from fastapi.testclient import TestClient
        from conftest import LoopbackPeer
        from app.auth import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: account
        yield TestClient(LoopbackPeer(app))
        app.dependency_overrides.pop(get_current_user, None)

    @staticmethod
    def _by_kind(res) -> dict:
        return {c["kind"]: c for c in res.json()["consents"]}

    def test_unpublished_kinds_are_absent(self, signed_in):
        """Một dòng "Chính sách X — (chưa có)" nói với người đọc một điều tổ
        chức không muốn nói, và cũng chẳng giúp gì cho họ."""
        _publish("terms", "1.0")
        items = self._by_kind(signed_in.get("/api/v1/legal/me/consents"))
        assert set(items) == {"terms"}

    def test_never_signed_reports_no_version(self, signed_in):
        _publish("data_contribution", "1.0", body="Đóng góp dữ liệu.")
        item = self._by_kind(signed_in.get("/api/v1/legal/me/consents"))["data_contribution"]
        assert item["accepted"] is False
        assert item["accepted_version"] is None
        assert item["accepted_at"] is None
        assert item["needs_reconsent"] is False

    def test_a_signature_names_its_version_and_time(self, signed_in, account):
        """Không có số hiệu bản đã ký thì nút "đọc lại bản tôi đã ký" không dựng
        được, và "bạn đã đồng ý" thành một câu không kiểm chứng được."""
        _publish("data_contribution", "1.0", body="Đóng góp dữ liệu.")
        legal.record_consent(account["id"], "data_contribution", "1.0")

        item = self._by_kind(signed_in.get("/api/v1/legal/me/consents"))["data_contribution"]
        assert item["accepted"] is True
        assert item["accepted_version"] == "1.0"
        assert item["accepted_at"]

    def test_signing_an_old_version_is_not_the_same_as_never_signing(
        self, signed_in, account
    ):
        """Gộp hai trạng thái này vào một chữ "Chưa" là nói với người đã từng
        đồng ý rằng họ chưa từng làm vậy."""
        _publish("data_contribution", "1.0", body="Bản một.")
        legal.record_consent(account["id"], "data_contribution", "1.0")
        legal.register_document("data_contribution", "2.0",
                                url="/legal/data_contribution",
                                body="Phạm vi mới.", requires_reconsent=True)

        item = self._by_kind(signed_in.get("/api/v1/legal/me/consents"))["data_contribution"]
        assert item["accepted"] is False
        assert item["needs_reconsent"] is True
        # Bản CŨ vẫn phải đọc lại được: nó là thứ người ta thật sự đã ký.
        assert item["accepted_version"] == "1.0"
        assert item["current_version"] == "2.0"

    def test_the_scope_a_signature_grants_is_named(self, signed_in):
        """Một nút "Đồng ý" trơ trọi biến một lần bấm thành giấy phép công bố
        khuôn mặt người ta. Ranh giới nằm trong bản văn (mục 4) và phải đi kèm
        cái nút."""
        _publish("terms", "1.0")
        _publish("data_contribution", "1.0", body="Đóng góp dữ liệu.")
        items = self._by_kind(signed_in.get("/api/v1/legal/me/consents"))

        assert items["data_contribution"]["grants_scope"] == "internal_training"
        # Ký điều khoản sử dụng KHÔNG cấp mức dữ liệu nào cả.
        assert items["terms"]["grants_scope"] is None

    def test_withdrawable_matches_what_the_server_actually_allows(
        self, signed_in, account
    ):
        """Cờ này tồn tại để giao diện khỏi tự suy. Nếu nó lệch khỏi hành vi
        thật thì trang sẽ hiện một cái nút chắc chắn trả 409 — đúng cái mà việc
        đưa cờ từ máy chủ xuống định tránh."""
        _publish("terms", "1.0")
        _publish("data_contribution", "1.0", body="Đóng góp dữ liệu.")
        legal.record_consent(account["id"], "terms", "1.0")
        legal.record_consent(account["id"], "data_contribution", "1.0")

        items = self._by_kind(signed_in.get("/api/v1/legal/me/consents"))
        assert items["terms"]["withdrawable"] is False
        assert items["data_contribution"]["withdrawable"] is True

        assert signed_in.post("/api/v1/legal/terms/withdraw").status_code == 409
        assert signed_in.post("/api/v1/legal/data_contribution/withdraw").status_code == 200

    def test_a_per_session_document_is_not_offered_as_a_one_time_signature(
        self, signed_in
    ):
        """`guardian` tự nói nó được hỏi trong TỪNG buổi ghi hình.

        Thu một chữ ký vĩnh viễn cho nó là thu đúng thứ bản văn ấy từ chối —
        "mỗi buổi thu là một lần bạn biết cụ thể hôm nay con em mình làm gì".
        Cờ này là thứ giữ cái nút đó khỏi xuất hiện.
        """
        _publish("guardian", "1.0", body="Người giám hộ.")
        _publish("data_contribution", "1.0", body="Đóng góp dữ liệu.")
        items = self._by_kind(signed_in.get("/api/v1/legal/me/consents"))

        assert items["guardian"]["self_signable"] is False
        assert items["data_contribution"]["self_signable"] is True

    def test_signing_through_the_api_shows_up_in_the_listing(self, signed_in):
        """Vòng khép kín mà toàn bộ phần B1 tồn tại để nối: bấm đồng ý ở giao
        diện → `user_consents` có dòng → lần đọc sau nói "đã đồng ý"."""
        _publish("data_contribution", "1.0", body="Đóng góp dữ liệu.")

        res = signed_in.post("/api/v1/legal/data_contribution/accept",
                             json={"version": "1.0"})
        assert res.status_code == 200, res.text

        item = self._by_kind(signed_in.get("/api/v1/legal/me/consents"))["data_contribution"]
        assert item["accepted"] is True
        assert item["accepted_version"] == "1.0"

    def test_signing_a_stale_version_is_refused(self, signed_in):
        """Một tab mở lâu ngày gửi số hiệu cũ. Nhận nó là thu chữ ký cho một bản
        văn đã bị thay thế."""
        _publish("data_contribution", "2.0", body="Bản hai.")
        res = signed_in.post("/api/v1/legal/data_contribution/accept",
                             json={"version": "1.0"})
        assert res.status_code == 409
        assert res.json()["detail"]["code"] == "stale_version"


def _purge(username: str) -> None:
    """Uỷ cho bản dùng chung ở conftest.

    Bản cũ ở đây chỉ xoá `users` + hai bảng con, viết cho thời một lượt đăng ký
    chèn đúng một hàng. Từ v4 nó còn tạo cả một tenant, và bản cũ để lại 5
    tenant mồ côi mỗi lượt chạy suite.
    """
    from conftest import purge_registered_account

    purge_registered_account(username)
