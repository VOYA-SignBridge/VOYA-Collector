"""Đường quản trị văn bản pháp lý: ai công bố được, và công bố để lại dấu gì.

Hai câu hỏi tệp này canh:

1. **Công bố có phải là thao tác được bảo vệ không.** Công bố một bản kèm
   `requires_reconsent` sẽ đá mọi người dùng đang hoạt động ra màn hình đồng ý,
   và bản vừa công bố không xoá lại được ngay khi có người đầu tiên ký. Một
   thao tác như vậy không nên chỉ cách một cú nhấp chuột.

2. **Dấu vết để lại có đúng thứ cần không.** Dòng kiểm toán phải mang HASH chứ
   không mang thân văn bản, và màn hình quản trị không được hiển thị băm địa chỉ
   IP của người dùng.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app import legal
from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


def _version() -> str:
    return f"adm-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def admin_account():
    """Một quản trị viên THẬT, không phải một dict giả.

    `published_by` là khoá ngoại UUID tới `users`, nên bản ghi đè quen dùng ở
    các tệp khác — `lambda: {"id": "t", ...}` — sẽ làm câu INSERT đổ vỡ vì `"t"`
    không phải UUID. Lỗi đó rất dễ đọc nhầm thành lỗi của endpoint.
    """
    from app.auth import create_user

    name = f"lgadm{uuid.uuid4().hex[:8]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery", is_admin=True)
    yield user
    from conftest import purge_registered_account

    purge_registered_account(name)


@pytest.fixture
def client(admin_account):
    from app.auth import require_admin
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: admin_account
    yield TestClient(app)
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def with_sudo(admin_account):
    from app import sudo_mode

    sudo_mode.grant(str(admin_account["id"]))
    yield
    sudo_mode.revoke(str(admin_account["id"]))


@pytest.fixture
def cleanup_versions():
    """Dọn đúng những bản mà test vừa công bố qua API.

    Không xoá sạch bảng: bộ test chạy trên bản sao của cơ sở dữ liệu sản xuất,
    nơi các bản điều khoản thật đang nằm.
    """
    created: list[tuple[str, str]] = []
    yield created
    with system_scope("test cleanup: gỡ các bản công bố qua API"):
        for kind, version in reversed(created):
            db._execute("DELETE FROM user_consents WHERE kind = %s AND version = %s",
                        (kind, version))
            db._execute("DELETE FROM legal_documents WHERE kind = %s AND version = %s",
                        (kind, version))


def _payload(**overrides) -> dict:
    body = {
        "kind": "terms",
        "version": _version(),
        "title": "Điều khoản thử",
        "body": "# Điều khoản\n\nMột đoạn.",
    }
    body.update(overrides)
    return body


# ===========================================================================
# Cổng: đọc cần quyền quản trị, GHI cần nâng quyền
# ===========================================================================

class TestPublishingIsAGuardedAction:
    def test_publish_withoutSudo_is403(self, client, cleanup_versions):
        """Không nâng quyền thì không công bố được, kể cả đã là quản trị viên."""
        response = client.post("/api/v1/admin/legal/documents", json=_payload())

        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "sudo_required"

    def test_publish_withSudo_is201(self, client, with_sudo, cleanup_versions):
        payload = _payload()

        response = client.post("/api/v1/admin/legal/documents", json=payload)

        assert response.status_code == 201, response.text
        cleanup_versions.append((payload["kind"], payload["version"]))

    def test_publish_withoutSudo_writesNothing(self, client, cleanup_versions):
        """Bị từ chối phải nghĩa là KHÔNG có gì xảy ra.

        Phản chứng cho một kiểu hỏng cụ thể: kiểm nâng quyền đặt sau lời gọi
        ghi. Khi đó phản hồi vẫn là 403 và test đầu tiên vẫn xanh.
        """
        payload = _payload()

        client.post("/api/v1/admin/legal/documents", json=payload)

        assert legal.admin_read_document("terms", payload["version"]) is None

    def test_listDocuments_needsNoSudo(self, client):
        """ĐỌC không cần nâng quyền. Bắt nâng quyền để xem sẽ khiến người ta
        nâng quyền theo thói quen — đúng thứ làm bước xác thực lại mất nghĩa."""
        response = client.get("/api/v1/admin/legal/documents")

        assert response.status_code == 200, response.text


# ===========================================================================
# Ngữ nghĩa công bố
# ===========================================================================

class TestPublishSemantics:
    def test_republishingIdenticalContent_isAccepted(
        self, client, with_sudo, cleanup_versions
    ):
        """Chạy lại kịch bản triển khai là chuyện bình thường."""
        payload = _payload()
        client.post("/api/v1/admin/legal/documents", json=payload)
        cleanup_versions.append((payload["kind"], payload["version"]))

        response = client.post("/api/v1/admin/legal/documents", json=payload)

        assert response.status_code == 201, response.text

    def test_changingContentUnderTheSameVersion_is409(
        self, client, with_sudo, cleanup_versions
    ):
        payload = _payload()
        client.post("/api/v1/admin/legal/documents", json=payload)
        cleanup_versions.append((payload["kind"], payload["version"]))

        response = client.post("/api/v1/admin/legal/documents",
                               json={**payload, "body": "Nội dung khác hẳn."})

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "version_content_mismatch"

    def test_publish_recordsWhoPublishedIt(
        self, client, with_sudo, cleanup_versions, admin_account
    ):
        payload = _payload()

        client.post("/api/v1/admin/legal/documents", json=payload)
        cleanup_versions.append((payload["kind"], payload["version"]))

        doc = legal.admin_read_document("terms", payload["version"])
        assert doc is not None
        assert str(doc["published_by"]) == str(admin_account["id"])

    def test_publishingForTheFuture_reportsScheduledNotApplied(
        self, client, with_sudo, cleanup_versions
    ):
        """Phản hồi phải phân biệt "đã lên lịch" với "đã áp dụng".

        Giao diện dựng câu thông báo từ đây; gộp hai trạng thái lại sẽ nói với
        người vận hành rằng điều khoản đã đổi trong khi nó chưa.
        """
        from datetime import datetime, timedelta, timezone

        later = datetime.now(timezone.utc) + timedelta(days=30)
        payload = _payload(effective_from=later.isoformat())

        response = client.post("/api/v1/admin/legal/documents", json=payload)
        cleanup_versions.append((payload["kind"], payload["version"]))

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["published"]["version"] == payload["version"]
        current = body["current"]
        assert current is None or current["version"] != payload["version"]

    def test_publishedResponse_omitsTheBody(
        self, client, with_sudo, cleanup_versions
    ):
        """Phản hồi xác nhận không cần gửi lại thứ người gọi vừa gửi lên."""
        payload = _payload(body="y" * 3000)

        response = client.post("/api/v1/admin/legal/documents", json=payload)
        cleanup_versions.append((payload["kind"], payload["version"]))

        assert "body" not in response.json()["published"]


# ===========================================================================
# Dấu vết
# ===========================================================================

class TestTheAuditTrail:
    def test_publish_writesAnAuditLineCarryingTheHashNotTheBody(
        self, client, with_sudo, cleanup_versions
    ):
        """Sổ kiểm toán được đọc và chuyển tiếp thường xuyên hơn bảng văn bản.

        Nhét cả bản văn vào đó là nhân bản một tài liệu có thể còn đang cấm phát
        hành, sang một chỗ có vòng đời và quyền đọc khác hẳn.
        """
        secret = "ĐOẠN VĂN KHÔNG ĐƯỢC XUẤT HIỆN TRONG SỔ KIỂM TOÁN"
        payload = _payload(body=f"# Điều khoản\n\n{secret}\n")

        client.post("/api/v1/admin/legal/documents", json=payload)
        cleanup_versions.append((payload["kind"], payload["version"]))

        with system_scope("test read: sổ kiểm toán"):
            rows = db._fetch_all(
                "SELECT detail::text AS d, target_id FROM audit_log "
                "WHERE action = 'legal.publish' AND target_id = %s",
                (f"terms:{payload['version']}",))

        assert rows, "không có dòng kiểm toán nào cho lần công bố"
        assert secret not in rows[0]["d"]
        assert legal.content_hash(payload["body"])[:16] in rows[0]["d"]


class TestReadingAUsersConsentHistory:
    def test_history_includesWithdrawnRows(self, client, with_sudo,
                                           cleanup_versions):
        """Câu hỏi bảng này tồn tại để trả lời là "đã đồng ý những gì, lúc nào",
        và câu đó chỉ trả lời được nếu các câu trả lời cũ còn nguyên."""
        from app.auth import create_user
        from conftest import purge_registered_account

        name = f"lghist{uuid.uuid4().hex[:8]}"
        user = create_user(username=name, email=f"{name}@example.test",
                           password="correct horse battery")
        try:
            first = _payload(version=_version(), body="Bản một.")
            client.post("/api/v1/admin/legal/documents", json=first)
            cleanup_versions.append(("terms", first["version"]))
            legal.record_consent(user["id"], "terms", first["version"])

            second = _payload(version=_version(), body="Bản hai.")
            client.post("/api/v1/admin/legal/documents", json=second)
            cleanup_versions.append(("terms", second["version"]))
            legal.record_consent(user["id"], "terms", second["version"])

            response = client.get(f"/api/v1/admin/legal/consents/{user['id']}")

            assert response.status_code == 200, response.text
            rows = response.json()["consents"]
            assert len(rows) == 2
            assert sum(1 for r in rows if r["withdrawn_at"] is not None) == 1
        finally:
            purge_registered_account(name)

    def test_history_neverShipsTheIpHash(self, client, with_sudo,
                                         cleanup_versions):
        """Băm địa chỉ là bằng chứng để đối chiếu, không phải thông tin để hiển
        thị: hiện nó trên màn hình không nói với người xem điều gì, mà lại là
        một mẩu dữ liệu cá nhân nữa đi ra ngoài."""
        from app.auth import create_user
        from conftest import purge_registered_account

        name = f"lgip{uuid.uuid4().hex[:8]}"
        user = create_user(username=name, email=f"{name}@example.test",
                           password="correct horse battery")
        try:
            payload = _payload()
            client.post("/api/v1/admin/legal/documents", json=payload)
            cleanup_versions.append(("terms", payload["version"]))
            legal.record_consent(user["id"], "terms", payload["version"],
                                 ip_hash="a" * 64)

            response = client.get(f"/api/v1/admin/legal/consents/{user['id']}")

            assert "ip_hash" not in response.json()["consents"][0]
            assert "a" * 64 not in response.text
        finally:
            purge_registered_account(name)


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setenv("LEGAL_STORE_ROOT", str(tmp_path / "legal"))


@pytest.fixture
def drafts():
    created: list[str] = []
    yield created
    with system_scope("test cleanup: gỡ bản nháp"):
        for draft_id in reversed(created):
            try:
                db._execute("DELETE FROM legal_document_drafts WHERE draft_id = %s",
                            (draft_id,))
            except Exception:
                pass


class TestTheDraftEditorApi:
    def test_createDraft_needsNoSudo(self, client, drafts):
        """Soạn thảo chưa thay đổi gì đối ngoại.

        Bắt nhập lại mật khẩu để MỞ một trang soạn thảo sẽ khiến người ta nâng
        quyền theo thói quen, và tới lúc thật sự cần — lúc công bố — cửa sổ nâng
        quyền đã mở sẵn. Đó là cách làm rỗng ý nghĩa của bước xác thực lại.
        """
        response = client.post("/api/v1/admin/legal/drafts",
                               json={"kind": "guardian", "seed_from_current": False})

        assert response.status_code == 201, response.text
        drafts.append(response.json()["draft_id"])

    def test_publishDraft_withoutSudo_is403(self, client, drafts, temp_store):
        draft = _approve_via_api(client, drafts, version=_version())

        response = client.post(
            f"/api/v1/admin/legal/drafts/{draft['draft_id']}/publish",
            json={"revision": draft["revision"]})

        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "sudo_required"

    def test_patchDraft_withAStaleRevision_returnsTheCurrentOne(self, client, drafts):
        """409 phải MANG THEO số hiệu hiện tại.

        Không có nó, giao diện chỉ biết "hỏng" và cách duy nhất còn lại là bảo
        người dùng tải lại trang — mất luôn đoạn họ vừa gõ.
        """
        created = client.post("/api/v1/admin/legal/drafts",
                              json={"kind": "guardian", "seed_from_current": False})
        draft = created.json()
        drafts.append(draft["draft_id"])
        client.patch(f"/api/v1/admin/legal/drafts/{draft['draft_id']}",
                     json={"revision": draft["revision"], "title": "A"})

        response = client.patch(f"/api/v1/admin/legal/drafts/{draft['draft_id']}",
                                json={"revision": draft["revision"], "title": "B"})

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["code"] == "revision_conflict"
        assert detail["current_revision"] == draft["revision"] + 1

    def test_patchDraft_onlySendsFieldsThatWereSet(self, client, drafts):
        """`exclude_unset` là thứ giữ cho một lượt sửa tiêu đề không âm thầm
        ghi đè thân bài bằng `None`."""
        created = client.post("/api/v1/admin/legal/drafts",
                              json={"kind": "guardian", "seed_from_current": False})
        draft = created.json()
        drafts.append(draft["draft_id"])
        client.patch(f"/api/v1/admin/legal/drafts/{draft['draft_id']}",
                     json={"revision": draft["revision"], "body": "# Thân bài"})

        fresh = client.get(f"/api/v1/admin/legal/drafts/{draft['draft_id']}").json()
        client.patch(f"/api/v1/admin/legal/drafts/{draft['draft_id']}",
                     json={"revision": fresh["revision"], "title": "Chỉ đổi tiêu đề"})

        after = client.get(f"/api/v1/admin/legal/drafts/{draft['draft_id']}").json()
        assert after["body"] == "# Thân bài"
        assert after["title"] == "Chỉ đổi tiêu đề"

    def test_publishDraft_withSudo_createsTheDocument(
        self, client, with_sudo, drafts, cleanup_versions, temp_store
    ):
        version = _version()
        draft = _approve_via_api(client, drafts, version=version)

        response = client.post(
            f"/api/v1/admin/legal/drafts/{draft['draft_id']}/publish",
            json={"revision": draft["revision"]})
        cleanup_versions.append(("guardian", version))

        assert response.status_code == 201, response.text
        assert response.json()["draft"]["published_version"] == version

    def test_eventsEndpoint_returnsTheRegisterNewestFirst(self, client, drafts):
        created = client.post("/api/v1/admin/legal/drafts",
                              json={"kind": "guardian", "seed_from_current": False})
        drafts.append(created.json()["draft_id"])

        response = client.get("/api/v1/admin/legal/events",
                              params={"kind": "guardian", "limit": 5})

        assert response.status_code == 200, response.text
        events = response.json()["events"]
        assert events and events[0]["action"] == "draft.create"

    def test_eventsEndpoint_namesTheActor(self, client, drafts, admin_account,
                                          free_legal_kinds):
        """Sổ phải trả lời được "AI làm" chứ không chỉ "có ai đó làm".

        Loại văn bản lấy động — xem `free_legal_kinds` trong conftest.
        """
        kind = free_legal_kinds[0]
        created = client.post("/api/v1/admin/legal/drafts",
                              json={"kind": kind, "seed_from_current": False})
        drafts.append(created.json()["draft_id"])

        events = client.get("/api/v1/admin/legal/events",
                            params={"kind": kind, "limit": 5}).json()

        assert events["events"][0]["actor"] == admin_account["username"]


def _approve_via_api(client, drafts, *, version: str) -> dict:
    created = client.post("/api/v1/admin/legal/drafts",
                          json={"kind": "guardian", "seed_from_current": False})
    draft = created.json()
    drafts.append(draft["draft_id"])
    draft = client.patch(
        f"/api/v1/admin/legal/drafts/{draft['draft_id']}",
        json={"revision": draft["revision"], "body": "# Bản\n\nNội dung.",
              "target_version": version, "title": "Người giám hộ"}).json()
    for status_name in ("in_review", "approved"):
        draft = client.post(
            f"/api/v1/admin/legal/drafts/{draft['draft_id']}/status",
            json={"revision": draft["revision"], "status": status_name}).json()
    return draft


class TestTheOverviewAnswersTheOperationalQuestion:
    def test_listDocuments_reportsWhichRequiredKindsAreMissing(self, client):
        """"Quên công bố" trông giống hệt "chạy bình thường" trên mọi màn hình
        khác. Đây là một trong hai chỗ nó lộ ra (chỗ kia là
        `verify_deployment`)."""
        response = client.get("/api/v1/admin/legal/documents")

        body = response.json()
        assert set(body["required_at_registration"]) == {"terms", "privacy"}
        assert set(body["missing_required"]) <= set(body["required_at_registration"])

    def test_listDocuments_carriesCoverageNumbers(self, client):
        response = client.get("/api/v1/admin/legal/documents")

        coverage = {row["kind"]: row for row in response.json()["coverage"]}
        assert set(coverage) == {"terms", "privacy"}
        for row in coverage.values():
            assert row["accepted_by_user"] <= row["accepted"]
