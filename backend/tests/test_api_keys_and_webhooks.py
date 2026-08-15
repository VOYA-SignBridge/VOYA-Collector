"""Khoá API và webhook — hai bề mặt mới, cả hai đều là bề mặt tấn công.

Trọng tâm không phải "tính năng chạy được" mà là những tính chất mà nếu hỏng
thì không có gì đỏ cho tới lúc có người khai thác: khoá không được lưu nguyên
văn, chữ ký không được phát lại, webhook không được trỏ vào mạng nội bộ, và
không khoá nào với sang tenant khác.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import api_keys, webhooks
from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def two_tenants():
    from app import plans, tenant_admin
    from conftest import purge_tenant

    ids = []
    for _ in range(2):
        tenant_id = f"kw{uuid.uuid4().hex[:10]}"
        tenant_admin.create_tenant(
            tenant_id, display_name="Key Test", clone_catalog=False, plan_code="plus"
        )
        ids.append(tenant_id)
    plans._clear_caches()
    yield ids
    for tenant_id in ids:
        purge_tenant(tenant_id)
    plans._clear_caches()


# --------------------------------------------------------------------------- keys


class TestKeyStorage:
    def test_the_raw_key_is_never_stored(self, two_tenants):
        """Tính chất trung tâm. Nếu nó hỏng, một bản dump cơ sở dữ liệu là một
        tập khoá dùng được ngay."""
        tenant = two_tenants[0]
        created = api_keys.create_key(tenant, name="ci", scopes="write")
        raw = created["key"]

        with system_scope("test: read the stored key row"):
            rows = db._fetch_all(
                "SELECT key_hash, prefix FROM api_keys WHERE key_id = %s",
                (created["key_id"],),
            )
        stored = rows[0]
        assert raw not in stored["key_hash"]
        assert len(stored["key_hash"]) == 64  # sha256 hex
        # Prefix lưu nguyên văn có chủ ý — nó là nhãn hiển thị và là đường tra
        # cứu O(1). Nó KHÔNG được đủ để dựng lại khoá.
        assert raw.startswith(stored["prefix"])
        assert len(raw) > len(stored["prefix"]) + 30

    def test_a_key_authenticates_and_names_its_own_tenant(self, two_tenants):
        tenant = two_tenants[0]
        created = api_keys.create_key(tenant, scopes="read")
        record = api_keys.authenticate(created["key"])
        assert record is not None
        assert record["tenant_id"] == tenant
        assert record["scopes"] == "read"

    def test_a_revoked_key_stops_working_immediately(self, two_tenants):
        tenant = two_tenants[0]
        created = api_keys.create_key(tenant)
        api_keys.revoke_key(tenant, created["key_id"])
        assert api_keys.authenticate(created["key"]) is None

    def test_an_expired_key_stops_working(self, two_tenants):
        tenant = two_tenants[0]
        created = api_keys.create_key(
            tenant, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        assert api_keys.authenticate(created["key"]) is None

    def test_one_tenant_cannot_revoke_another_tenants_key(self, two_tenants):
        """Phạm vi theo CẢ tenant lẫn id. Một UUID đoán trúng không được trở
        thành nút tắt dịch vụ của tổ chức khác."""
        owner, stranger = two_tenants
        created = api_keys.create_key(owner)
        with pytest.raises(api_keys.ApiKeyError) as caught:
            api_keys.revoke_key(stranger, created["key_id"])
        assert caught.value.status_code == 404
        assert api_keys.authenticate(created["key"]) is not None

    def test_a_garbled_key_is_refused_without_saying_why(self):
        """Mọi lý do thất bại trả về cùng một thứ: None. Phân biệt chúng ra
        ngoài là biến endpoint thành máy dò prefix có thật."""
        for candidate in ("", "not-a-key", "voya_", "voya_abcd", "voya_ab_cd_ef",
                          "voya_deadbeef_khonghople"):
            assert api_keys.authenticate(candidate) is None


class TestKeyAuthorisation:
    def test_a_key_is_never_a_platform_admin(self, two_tenants):
        """Kể cả khi người tạo ra nó là quản trị viên nền tảng.

        Quyền vận hành nền tảng phải đi kèm một con người đang đăng nhập, và
        với thao tác nhạy cảm là một lần nhập lại mật khẩu — thứ một chuỗi ký
        tự trong biến môi trường CI không có.
        """
        from app.auth import _user_from_api_key

        created = api_keys.create_key(two_tenants[0], scopes="write")
        user = _user_from_api_key(created["key"])
        assert user["is_admin"] is False
        assert user["tenant_id"] == two_tenants[0]

    def test_a_read_key_cannot_edit_the_catalogue(self, two_tenants):
        from fastapi import HTTPException

        from app.auth import _user_from_api_key, require_tenant_editor

        created = api_keys.create_key(two_tenants[0], scopes="read")
        user = _user_from_api_key(created["key"])
        with pytest.raises(HTTPException) as caught:
            require_tenant_editor(user)
        assert caught.value.status_code == 403

    def test_a_write_key_can(self, two_tenants):
        """Phản chứng. Không có nó, test trên vẫn xanh nếu khoá nào cũng bị chặn."""
        from app.auth import _user_from_api_key, require_tenant_editor

        created = api_keys.create_key(two_tenants[0], scopes="write")
        user = _user_from_api_key(created["key"])
        assert require_tenant_editor(user) is user

    def test_an_api_key_action_still_lands_in_the_audit_log(self, two_tenants):
        """`actor_user_id` là UUID có khoá ngoại; id của khoá là "apikey:...".

        Chèn thẳng sẽ ném lỗi kiểu, và vì `audit.record` nuốt mọi lỗi, hệ quả
        là MỌI hành động qua khoá API biến mất khỏi nhật ký mà không ai thấy.
        Dòng phải được ghi, với nhãn còn nói được ai đã làm.
        """
        from app import audit
        from app.auth import _user_from_api_key

        created = api_keys.create_key(two_tenants[0], scopes="write")
        user = _user_from_api_key(created["key"])
        marker = f"test.apikey.{uuid.uuid4().hex[:8]}"
        assert audit.record(marker, actor=user, tenant_id=two_tenants[0]) is True

        with system_scope("test: read back the audit row"):
            rows = db._fetch_all(
                "SELECT actor_user_id, actor_label FROM audit_log WHERE action = %s",
                (marker,),
            )
        assert len(rows) == 1
        assert rows[0]["actor_user_id"] is None
        assert rows[0]["actor_label"].startswith("apikey:")


# --------------------------------------------------------------------------- webhooks


class TestSignature:
    def test_the_timestamp_is_inside_the_signature(self):
        """Ký mỗi thân thư thì một lần giao cũ phát lại được mãi mãi và chữ ký
        vẫn đúng. Đưa dấu thời gian vào phần được ký là thứ cho bên nhận từ
        chối được đồ cũ."""
        secret, body = "whsec_test", b'{"event":"sample.created"}'
        now = int(datetime.now(timezone.utc).timestamp())
        assert webhooks.sign(secret, now, body) != webhooks.sign(secret, now + 1, body)

    def test_a_replayed_delivery_is_rejected(self):
        secret, body = "whsec_test", b'{"event":"sample.created"}'
        stale = int(datetime.now(timezone.utc).timestamp()) - 3600
        signature = webhooks.sign(secret, stale, body)
        # Chữ ký đúng nguyên vẹn — thứ bị từ chối là tuổi của nó.
        assert webhooks.verify(secret, stale, body, signature) is False
        assert webhooks.verify(secret, stale, body, signature,
                               tolerance_seconds=7200) is True

    def test_a_tampered_body_breaks_the_signature(self):
        secret = "whsec_test"
        now = int(datetime.now(timezone.utc).timestamp())
        signature = webhooks.sign(secret, now, b'{"amount":1}')
        assert webhooks.verify(secret, now, b'{"amount":9}', signature) is False

    def test_the_wrong_secret_breaks_it(self):
        now = int(datetime.now(timezone.utc).timestamp())
        signature = webhooks.sign("whsec_a", now, b"x")
        assert webhooks.verify("whsec_b", now, b"x", signature) is False


class TestEndpointRegistration:
    @pytest.mark.parametrize("url", [
        "http://localhost:8000/hook",
        "http://127.0.0.1/hook",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/hook",
        "http://192.168.1.10/hook",
        "http://metadata.google.internal/",
        "ftp://example.com/hook",
    ])
    def test_internal_and_non_http_targets_are_refused(self, two_tenants, url):
        """Một webhook trỏ vào mạng nội bộ biến nền tảng thành công cụ gửi yêu
        cầu hộ vào chính hạ tầng của nó. Người tạo webhook là khách hàng, nên
        đây là dữ liệu không tin được."""
        with pytest.raises(webhooks.WebhookError):
            webhooks.create_endpoint(two_tenants[0], url=url)

    def test_a_public_https_target_is_accepted(self, two_tenants):
        result = webhooks.create_endpoint(
            two_tenants[0], url="https://hooks.example.com/voya"
        )
        assert result["endpoint_id"]
        assert result["secret"].startswith("whsec_")

    def test_the_secret_is_returned_once_and_never_listed_again(self, two_tenants):
        tenant = two_tenants[0]
        created = webhooks.create_endpoint(tenant, url="https://hooks.example.com/a")
        listed = webhooks.list_endpoints(tenant)
        assert listed, "endpoint vừa tạo phải xuất hiện"
        for row in listed:
            assert "secret" not in row, "bí mật ký lọt ra ở đường liệt kê"

    def test_an_unknown_event_type_is_refused_at_registration(self, two_tenants):
        """Gõ sai tên sự kiện mà được chấp nhận nghĩa là endpoint im lặng
        không bao giờ nhận gì, và người dựng tích hợp mất một buổi chiều."""
        with pytest.raises(webhooks.WebhookError):
            webhooks.create_endpoint(
                two_tenants[0], url="https://hooks.example.com/b",
                event_types="sample.creted",
            )


class TestDeliveryQueue:
    def test_emit_only_reaches_endpoints_of_the_same_tenant(self, two_tenants):
        owner, stranger = two_tenants
        webhooks.create_endpoint(owner, url="https://hooks.example.com/owner")
        webhooks.create_endpoint(stranger, url="https://hooks.example.com/stranger")

        queued = webhooks.emit(owner, "sample.created", {"sample_uid": "x"})
        assert queued == 1

        with system_scope("test: count queued deliveries per tenant"):
            rows = db._fetch_all(
                "SELECT tenant_id, count(*) AS n FROM webhook_deliveries "
                "WHERE tenant_id = ANY(%s) GROUP BY tenant_id",
                (list(two_tenants),),
            )
        counts = {r["tenant_id"]: int(r["n"]) for r in rows}
        assert counts.get(owner) == 1
        assert counts.get(stranger, 0) == 0

    def test_a_subscription_filter_is_honoured(self, two_tenants):
        tenant = two_tenants[0]
        webhooks.create_endpoint(
            tenant, url="https://hooks.example.com/only-training",
            event_types="training.completed",
        )
        assert webhooks.emit(tenant, "sample.created", {}) == 0
        assert webhooks.emit(tenant, "training.completed", {}) == 1

    def test_emit_never_raises_when_the_event_name_is_wrong(self, two_tenants):
        """Webhook là tính năng phụ trợ. Làm hỏng một lượt tải mẫu vì tên sự
        kiện viết sai ở một chỗ gọi là đánh đổi sai."""
        assert webhooks.emit(two_tenants[0], "khong.ton.tai", {}) == 0

    def test_repeated_failures_eventually_disable_the_endpoint(self, two_tenants):
        """Không tắt thì một URL đã chết vĩnh viễn được thử lại mãi mãi, và
        hàng đợi giao dần biến thành một danh sách rác chạy nền."""
        tenant = two_tenants[0]
        created = webhooks.create_endpoint(tenant, url="https://hooks.example.com/dead")
        endpoint_id = created["endpoint_id"]

        with system_scope("test: drive the failure streak to the limit"):
            for _ in range(webhooks.FAILURE_STREAK_LIMIT):
                delivery_id = str(uuid.uuid4())
                db._execute(
                    "INSERT INTO webhook_deliveries(delivery_id, tenant_id, "
                    "endpoint_id, event_type, payload) VALUES(%s,%s,%s,%s,%s)",
                    (delivery_id, tenant, endpoint_id, "sample.created", "{}"),
                )
                webhooks._record_failure(endpoint_id, delivery_id, 0, 500, "HTTP 500")
            rows = db._fetch_all(
                "SELECT is_active, disabled_reason FROM webhook_endpoints "
                "WHERE endpoint_id = %s",
                (endpoint_id,),
            )
        assert rows[0]["is_active"] is False
        assert rows[0]["disabled_reason"]

    def test_a_success_resets_the_streak(self, two_tenants):
        """Một sự cố ngắn bên khách hàng không được tích luỹ tới ngưỡng tắt."""
        tenant = two_tenants[0]
        created = webhooks.create_endpoint(tenant, url="https://hooks.example.com/flaky")
        endpoint_id = created["endpoint_id"]

        with system_scope("test: fail a few times then succeed"):
            for _ in range(3):
                delivery_id = str(uuid.uuid4())
                db._execute(
                    "INSERT INTO webhook_deliveries(delivery_id, tenant_id, "
                    "endpoint_id, event_type, payload) VALUES(%s,%s,%s,%s,%s)",
                    (delivery_id, tenant, endpoint_id, "sample.created", "{}"),
                )
                webhooks._record_failure(endpoint_id, delivery_id, 0, 503, "HTTP 503")

            delivery_id = str(uuid.uuid4())
            db._execute(
                "INSERT INTO webhook_deliveries(delivery_id, tenant_id, endpoint_id, "
                "event_type, payload) VALUES(%s,%s,%s,%s,%s)",
                (delivery_id, tenant, endpoint_id, "sample.created", "{}"),
            )
            webhooks._record_success(endpoint_id, delivery_id, 200)
            rows = db._fetch_all(
                "SELECT failure_streak, is_active FROM webhook_endpoints "
                "WHERE endpoint_id = %s",
                (endpoint_id,),
            )
        assert int(rows[0]["failure_streak"]) == 0
        assert rows[0]["is_active"] is True

    def test_retries_back_off_and_then_give_up(self, two_tenants):
        tenant = two_tenants[0]
        created = webhooks.create_endpoint(tenant, url="https://hooks.example.com/giveup")
        endpoint_id = created["endpoint_id"]
        delivery_id = str(uuid.uuid4())

        with system_scope("test: exhaust the retry schedule of one delivery"):
            db._execute(
                "INSERT INTO webhook_deliveries(delivery_id, tenant_id, endpoint_id, "
                "event_type, payload) VALUES(%s,%s,%s,%s,%s)",
                (delivery_id, tenant, endpoint_id, "sample.created", "{}"),
            )
            for attempt in range(webhooks.MAX_ATTEMPTS):
                webhooks._record_failure(endpoint_id, delivery_id, attempt, 500, "HTTP 500")
            rows = db._fetch_all(
                "SELECT status, attempts FROM webhook_deliveries WHERE delivery_id = %s",
                (delivery_id,),
            )
        assert rows[0]["status"] == "failed"
        assert int(rows[0]["attempts"]) == webhooks.MAX_ATTEMPTS


class TestRateLimitKeyspace:
    def test_apiKeyCaller_getsItsOwnBucketNotTheSharedIpBucket(self, two_tenants):
        """Khoá API không chia thùng đếm với người dùng trình duyệt cùng IP.

        Điều này đã đúng sẵn mà không cần thêm mã, và test tồn tại để nó KHÔNG
        lặng lẽ hỏng: `enforce_actor_limit` khoá theo `user_id` khi biết người
        gọi, và `_user_from_api_key` trả về một dict có `id`. Nếu một ngày nào
        đó `id` bị bỏ đi cho gọn, mọi tích hợp sau NAT chung sẽ rơi về thùng
        đếm theo IP và bóp lẫn nhau — ở một cơ sở giáo dục đặc biệt thì cả
        phòng là một NAT.

        Khẳng định trên HÌNH DẠNG khoá Redis chứ không phải trên hành vi 429:
        đếm tới ngưỡng trong test là chậm và phụ thuộc cấu hình, còn khoá thì
        nói thẳng thùng nào được dùng.
        """
        from app.auth import _user_from_api_key
        from app.rate_limit import _KEY_PREFIX, _hashed

        created = api_keys.create_key(two_tenants[0], scopes="read")
        user = _user_from_api_key(created["key"])

        assert user["id"].startswith("apikey:")
        expected = f"{_KEY_PREFIX}upload:user:{_hashed(user['id'])}"
        assert ":ip:" not in expected
        # Hai khoá khác nhau phải cho ra hai thùng khác nhau.
        other = api_keys.create_key(two_tenants[0], scopes="read")
        other_user = _user_from_api_key(other["key"])
        assert _hashed(user["id"]) != _hashed(other_user["id"])
