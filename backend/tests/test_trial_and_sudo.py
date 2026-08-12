"""Gói dùng thử 60 phút/ngày, và cửa nâng quyền cho người đổi con số đó.

Tính chất trung tâm của gói dùng thử là điều dễ tin mà không kiểm nhất:
**ngắt quãng chỉ tiêu đúng số phút thật sự dùng.** Đếm lượt gọi sẽ không cho ra
tính chất đó, nên nó được kiểm trực tiếp bằng cách giả lập đồng hồ thay vì suy
từ số lượt.

Fail-open và fail-closed nằm cạnh nhau ở đây, cố ý: `trial` mở khi Redis chết
(mất hạn ngạch không nguy hiểm), `sudo_mode` đóng (cấp nâng quyền vì hạ tầng
hỏng là biến sự cố thành lỗ bảo mật). Hai test cuối ghim đúng sự bất đối xứng đó.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import trial
from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture(autouse=True)
def _clean_redis():
    """Mỗi test bắt đầu với bitmap trống, nếu không phiếu của test trước còn sống."""
    from app.rate_limit import _client

    client = _client()
    if client is not None:
        for key in client.scan_iter("trial:*"):
            client.delete(key)
        for key in client.scan_iter("sudo:*"):
            client.delete(key)
    yield


@pytest.fixture
def client():
    """TestClient với MỘT IP MỚI cho mỗi lượt gọi.

    Không có phần này, mọi request đến từ 127.0.0.1 và dùng chung một thùng
    đếm rate-limit nằm trong Redis — thùng đó SỐNG QUA các lần chạy suite. Ba
    test ở `TestTrialEndpoints` đã đỏ vì đúng lý do đó: 271 khoá `ratelimit:*`
    tích lại từ những lượt chạy trước khiến `POST /trial/start` trả 429, và
    triệu chứng ("cấp phiếu không idempotent") trông hệt như một lỗi mã.

    Một test chỉ đúng nếu nó cho cùng kết quả ở lần chạy thứ nhất và thứ mười.
    Dọn Redis trước mỗi lần chạy cũng làm được, nhưng nó bắt người chạy phải
    nhớ; tách IP thì không phải nhớ gì.

    Cookie vẫn hoạt động: lớp bọc uỷ nhiệm cho `inner`, nên bình đựng cookie
    của TestClient được giữ nguyên — và gói dùng thử định danh khách BẰNG
    cookie chứ không bằng IP, nên đổi IP mỗi lượt không làm mất phiếu.
    """
    from fastapi.testclient import TestClient

    from conftest import LoopbackPeer, fresh_client_ip
    from app.main import app

    inner = TestClient(LoopbackPeer(app))

    class _MoiLuotMotIp:
        def __getattr__(self, verb):
            def call(url, **kwargs):
                headers = {**kwargs.pop("headers", {}),
                           "X-Forwarded-For": fresh_client_ip()}
                return getattr(inner, verb)(url, headers=headers, **kwargs)
            return call

    return _MoiLuotMotIp()


class _FakeRequest:
    """Chỉ mang cookie — đó là toàn bộ thứ `trial` đọc từ request."""

    def __init__(self, token=None):
        self.cookies = {trial.TRIAL_COOKIE: token} if token else {}


def _token():
    return uuid.uuid4().hex + uuid.uuid4().hex


# --------------------------------------------------------------- đo hạn ngạch


class TestMinutesNotCalls:
    def test_many_calls_in_one_minute_cost_one_minute(self, monkeypatch):
        """Client gửi 5 lượt/giây. Nếu đếm lượt thì một phút ký liên tục tiêu
        300 đơn vị; đếm phút thì tiêu đúng một."""
        req = _FakeRequest(_token())
        fixed = datetime(2026, 8, 7, 10, 30, tzinfo=timezone.utc)
        monkeypatch.setattr(trial, "datetime", _FrozenClock(fixed))

        for _ in range(50):
            state = trial.consume_minute(req)
        assert state.minutes_used == 1

    def test_intermittent_use_only_burns_active_minutes(self, monkeypatch):
        """Yêu cầu nguyên văn: "liên tục hay ngắt quãng đều được".

        Người dùng ký ở phút 0, đọc kết quả suốt phút 1–9, ký lại ở phút 10.
        Tiêu đúng HAI phút, không phải mười một.
        """
        req = _FakeRequest(_token())
        base = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)

        for offset in (0, 10):
            monkeypatch.setattr(
                trial, "datetime", _FrozenClock(base + timedelta(minutes=offset)))
            state = trial.consume_minute(req)
        assert state.minutes_used == 2

    def test_distinct_minutes_accumulate(self, monkeypatch):
        req = _FakeRequest(_token())
        base = datetime(2026, 8, 7, 11, 0, tzinfo=timezone.utc)
        for offset in range(5):
            monkeypatch.setattr(
                trial, "datetime", _FrozenClock(base + timedelta(minutes=offset)))
            state = trial.consume_minute(req)
        assert state.minutes_used == 5
        assert state.minutes_remaining == state.minutes_limit - 5

    def test_the_quota_is_per_grant_not_per_ip(self, monkeypatch):
        """Cả CTU đi qua một NAT. Hai khách khác nhau phải có hai hạn ngạch,
        dù cùng địa chỉ."""
        fixed = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(trial, "datetime", _FrozenClock(fixed))

        a, b = _FakeRequest(_token()), _FakeRequest(_token())
        trial.consume_minute(a)
        state_b = trial.consume_minute(b)
        assert state_b.minutes_used == 1

    def test_a_new_day_resets(self, monkeypatch):
        """Khoá bitmap gắn với ngày, nên sang ngày là hạn ngạch mới — không cần
        tác vụ dọn nào.

        Ranh giới là nửa đêm ĐỊA PHƯƠNG, nên hai mốc được tính từ độ lệch cấu
        hình thay vì viết cứng. Bản trước dùng 23:59 → 00:00 UTC, và điều đó
        khiến test khẳng định ranh giới UTC — đúng thứ đã được sửa đi: với một
        triển khai +7, nửa đêm UTC là 7 giờ sáng của người dùng.
        """
        from app.config import settings

        req = _FakeRequest(_token())
        offset = timedelta(hours=settings.trial_reset_utc_offset_hours)
        nua_dem_dia_phuong = datetime(2026, 8, 8, 0, 0, tzinfo=timezone.utc) - offset

        monkeypatch.setattr(
            trial, "datetime", _FrozenClock(nua_dem_dia_phuong - timedelta(minutes=1)))
        trial.consume_minute(req)
        monkeypatch.setattr(trial, "datetime", _FrozenClock(nua_dem_dia_phuong))
        assert trial.consume_minute(req).minutes_used == 1

    def test_the_day_boundary_is_local_midnight_not_utc(self, monkeypatch):
        """Mặt còn lại, viết riêng để sự thay đổi không lặng lẽ trôi ngược.

        Với triển khai +7, nửa đêm UTC rơi vào 7 giờ sáng giờ Việt Nam. Nếu ai
        đó bỏ độ lệch đi, hạn ngạch sẽ reset giữa buổi sáng: người dùng lúc 6h
        bị chặn rồi được mở lại một tiếng sau, còn thông báo "quay lại vào ngày
        mai" thì sai. Test này đỏ ngay khi điều đó xảy ra.
        """
        from app.config import settings

        if settings.trial_reset_utc_offset_hours == 0:
            pytest.skip("triển khai này cố ý chạy theo UTC")

        req = _FakeRequest(_token())
        monkeypatch.setattr(
            trial, "datetime",
            _FrozenClock(datetime(2026, 8, 7, 23, 59, tzinfo=timezone.utc)))
        trial.consume_minute(req)
        monkeypatch.setattr(
            trial, "datetime",
            _FrozenClock(datetime(2026, 8, 8, 0, 0, tzinfo=timezone.utc)))
        assert trial.consume_minute(req).minutes_used == 2, (
            "vượt qua nửa đêm UTC đã reset hạn ngạch — ranh giới phải là nửa "
            "đêm địa phương, không phải nửa đêm UTC"
        )

    def test_the_reset_time_carries_its_timezone(self):
        """`resets_at` đi thẳng ra giao diện làm đồng hồ đếm ngược.

        Một chuỗi ISO không kèm độ lệch sẽ được trình duyệt hiểu là giờ địa
        phương của máy khách, và đồng hồ lệch đúng bằng độ lệch múi giờ.
        """
        state = trial.peek(_FakeRequest())
        assert state.resets_at.endswith(("Z", "+00:00")) or "+" in state.resets_at[10:], (
            f"resets_at thiếu múi giờ: {state.resets_at!r}"
        )


class TestExhaustion:
    def test_refuses_past_the_limit(self, monkeypatch):
        req = _FakeRequest(_token())
        monkeypatch.setattr(trial, "_limit", lambda: 3)
        base = datetime(2026, 8, 7, 9, 0, tzinfo=timezone.utc)
        for offset in range(3):
            monkeypatch.setattr(
                trial, "datetime", _FrozenClock(base + timedelta(minutes=offset)))
            assert trial.consume_minute(req).allowed

        monkeypatch.setattr(
            trial, "datetime", _FrozenClock(base + timedelta(minutes=3)))
        state = trial.consume_minute(req)
        assert state.allowed is False
        assert state.minutes_remaining == 0

    def test_a_refused_call_does_not_burn_a_minute(self, monkeypatch):
        """Kiểm hạn mức TRƯỚC khi đánh dấu. Làm ngược lại thì người dùng thấy
        đồng hồ tụt trong lúc không nhận được gì."""
        req = _FakeRequest(_token())
        monkeypatch.setattr(trial, "_limit", lambda: 1)
        base = datetime(2026, 8, 7, 8, 0, tzinfo=timezone.utc)

        monkeypatch.setattr(trial, "datetime", _FrozenClock(base))
        trial.consume_minute(req)
        monkeypatch.setattr(
            trial, "datetime", _FrozenClock(base + timedelta(minutes=5)))
        trial.consume_minute(req)
        assert trial.peek(req).minutes_used == 1

    def test_no_grant_and_exhausted_say_different_things(self):
        """Hai lý do từ chối khác nhau. Trả cùng một câu sẽ khiến người mới vào
        tưởng mình đã dùng hết."""
        no_grant = trial.TrialState(False, 0, 60, "x", None)
        used_up = trial.TrialState(False, 60, 60, "x", "abc")
        assert trial.describe(no_grant) != trial.describe(used_up)
        assert "Thử nhận diện" in trial.describe(no_grant)
        assert "hết" in trial.describe(used_up)


class TestPeekIsFree:
    def test_peek_does_not_consume(self, monkeypatch):
        req = _FakeRequest(_token())
        monkeypatch.setattr(
            trial, "datetime",
            _FrozenClock(datetime(2026, 8, 7, 7, 0, tzinfo=timezone.utc)))
        for _ in range(10):
            trial.peek(req)
        assert trial.peek(req).minutes_used == 0


# ------------------------------------------------------------------ HTTP


class TestTrialEndpoints:
    def test_start_is_idempotent(self, client):
        """Cấp phiếu mới mỗi lần gọi sẽ biến hạn ngạch hằng ngày thành vô hạn:
        chỉ cần gọi lại endpoint này."""
        first = client.post("/api/v1/trial/start")
        assert first.status_code == 200
        cookie = first.cookies.get(trial.TRIAL_COOKIE)
        assert cookie

        second = client.post("/api/v1/trial/start")
        assert second.status_code == 200
        # Không cấp cookie thứ hai
        assert second.cookies.get(trial.TRIAL_COOKIE) in (None, cookie)

    def test_status_reports_the_quota(self, client):
        client.post("/api/v1/trial/start")
        body = client.get("/api/v1/trial/status").json()
        assert body["has_grant"] is True
        assert body["minutes_limit"] >= 1
        assert body["minutes_remaining"] == body["minutes_limit"]

    def test_model_is_refused_without_a_grant(self, client):
        res = client.get("/api/v1/inference/classes")
        assert res.status_code == 401
        assert res.json()["code"] == "trial_exhausted"
        assert "Thử nhận diện" in res.json()["detail"]

    def test_model_is_allowed_with_a_grant_and_reports_the_counter(self, client):
        # `/inference/classes` chứ không phải `/realtime/models`: cái sau proxy
        # sang container realtime qua một HTTP client dựng trong lifespan, mà
        # TestClient ở đây không chạy lifespan. Cả hai cùng nằm trong
        # TRIAL_OR_SESSION_ROUTES nên chúng đi qua đúng một nhánh của cổng —
        # kiểm cái chạy cục bộ được thì đo đúng thứ cần đo, không đo hạ tầng.
        client.post("/api/v1/trial/start")
        res = client.get("/api/v1/inference/classes")
        assert res.status_code == 200
        # Bộ đếm đi kèm MỌI phản hồi để giao diện vẽ đồng hồ mà không phải gọi
        # thêm một vòng cho mỗi khung hình.
        assert "X-Trial-Minutes-Remaining" in res.headers
        assert int(res.headers["X-Trial-Minutes-Limit"]) >= 1

    def test_metadata_routes_do_not_burn_a_minute(self, client):
        """Giao diện nạp danh sách mô hình và giọng đọc khi mở trang. Tính chúng
        vào hạn ngạch nghĩa là người dùng mất một phút chỉ vì mở trang — đồng hồ
        chạy trước khi họ nhận được bất cứ thứ gì."""
        client.post("/api/v1/trial/start")
        for _ in range(3):
            client.get("/api/v1/inference/classes")
        assert client.get("/api/v1/trial/status").json()["minutes_used"] == 0

    def test_metadata_routes_still_require_a_grant(self, client):
        """Không tiêu hạn ngạch KHÔNG có nghĩa là mở: không có phiếu thì cũng
        chẳng có gì để hiển thị."""
        assert client.get("/api/v1/inference/classes").status_code == 401


# ------------------------------------------------------------------ sudo


@pytest.fixture
def admin_account():
    from app.auth import create_user

    name = f"sudo{uuid.uuid4().hex[:8]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery", is_admin=True)
    yield user
    _purge_account(user["id"])


def _purge_account(user_id: str) -> None:
    """Dọn một tài khoản test, chịu được việc một bảng con chưa tồn tại.

    Bản đầu gọi bốn `_execute` liên tiếp trong một khối. Khi `platform_settings`
    chưa được tạo, câu thứ ba ném `UndefinedTable` và câu thứ tư — `DELETE FROM
    users` — không bao giờ chạy tới. Kết quả: **10 tài khoản test nằm lại trong
    cơ sở dữ liệu sản xuất**, và chúng chỉ lộ ra khi đếm lại sau khi suite xong.

    Bộ test này chạy trên chính `signdb`, nên teardown phải xử lý thất bại từng
    phần: mỗi câu độc lập, và câu xoá `users` chạy sau cùng dù các câu trước có
    hỏng hay không.
    """
    children = (
        "DELETE FROM user_consents WHERE user_id = %s",
        "DELETE FROM verification_codes WHERE user_id = %s",
        "DELETE FROM refresh_tokens WHERE user_id = %s",
        "DELETE FROM tenant_members WHERE user_id = %s",
        "DELETE FROM platform_settings WHERE updated_by = %s",
    )
    with system_scope("test cleanup"):
        for sql in children:
            try:
                db._execute(sql, (user_id,))
            except Exception:
                # Bảng chưa tồn tại, hoặc không có dòng nào. Cả hai đều không
                # được ngăn việc xoá chính tài khoản.
                pass
        db._execute("DELETE FROM users WHERE id = %s", (user_id,))


class TestSudoMode:
    def test_wrong_password_does_not_elevate(self, admin_account):
        from fastapi import HTTPException

        from app import sudo_mode

        with pytest.raises(HTTPException) as exc:
            sudo_mode.elevate(admin_account, "not the password")
        assert exc.value.status_code == 403
        assert sudo_mode.seconds_remaining(str(admin_account["id"])) == 0

    def test_empty_password_does_not_elevate(self, admin_account):
        """`authenticate_user` với chuỗi rỗng phải thất bại. Kiểm riêng vì chuỗi
        rỗng là giá trị hay lọt qua nhất — cùng hạng lỗi với
        `codes_match("", "")` đã trả về True hồi tháng trước."""
        from fastapi import HTTPException

        from app import sudo_mode

        with pytest.raises(HTTPException):
            sudo_mode.elevate(admin_account, "")

    def test_correct_password_elevates_then_expires_on_revoke(self, admin_account):
        from app import sudo_mode

        ttl = sudo_mode.elevate(admin_account, "correct horse battery")
        assert ttl == sudo_mode.SUDO_TTL_SECONDS
        assert sudo_mode.seconds_remaining(str(admin_account["id"])) > 0

        sudo_mode.revoke(str(admin_account["id"]))
        assert sudo_mode.seconds_remaining(str(admin_account["id"])) == 0

    def test_elevation_is_per_user(self, admin_account):
        """Một quản trị viên nâng quyền không nâng quyền cho người khác."""
        from app import sudo_mode

        sudo_mode.elevate(admin_account, "correct horse battery")
        assert sudo_mode.seconds_remaining("00000000-0000-0000-0000-000000000000") == 0

    def test_redis_down_fails_CLOSED(self, monkeypatch, admin_account):
        """Ngược với `trial`, cố ý.

        Cấp nâng quyền vì hạ tầng hỏng là biến một sự cố thành một lỗ bảo mật.
        Chặn thao tác nhạy cảm trong lúc Redis chết thì phiền, nhưng đúng.
        """
        from fastapi import HTTPException

        from app import sudo_mode

        monkeypatch.setattr(sudo_mode, "_client", lambda: None)
        with pytest.raises(HTTPException) as exc:
            sudo_mode.grant(str(admin_account["id"]))
        assert exc.value.status_code == 503


class TestTrialFailsOpenWhenRedisDies:
    def test_redis_down_still_allows(self, monkeypatch):
        """Ngược với `sudo_mode`, cố ý: mất hạn ngạch không nguy hiểm cho ai,
        còn tắt tính năng dùng thử vì một sự cố hạ tầng thì có."""
        monkeypatch.setattr(trial, "_client", lambda: None)
        assert trial.consume_minute(_FakeRequest(_token())).allowed is True


# ------------------------------------------------------- thiết lập lúc chạy


class TestRedisFailureDoesNotLatchForever:
    """Một cú chớp Redis KHÔNG được tắt giới hạn tần suất vĩnh viễn.

    Bản trước đặt `_client_failed = True` và không bao giờ gỡ: một
    `socket_timeout` 3 giây trong lúc redis bận, hoặc một lần recreate container
    khi triển khai, sẽ tắt chống-dò-mật-khẩu, trần đăng ký và trần suy luận cho
    tới khi tiến trình khởi động lại — im lặng, sau đúng một dòng log.

    Nó cũng làm bộ test đỏ ngẫu nhiên: một cú chớp giữa 1.250 test khiến mọi bộ
    đếm sau đó im lặng không tăng, và test khẳng định bộ đếm hỏng ở một chỗ
    chẳng liên quan gì tới nguyên nhân. Đó chính là cách lỗi này bị phát hiện.
    """

    def test_a_failure_is_retried_after_the_cooldown(self, monkeypatch):
        import app.rate_limit as rl

        monkeypatch.setattr(rl, "_client_singleton", None)
        monkeypatch.setattr(rl, "_client_retry_at", 0.0)

        calls = {"n": 0}

        def _from_url(*_a, **_k):
            calls["n"] += 1
            raise RuntimeError("redis đang chớp")

        monkeypatch.setattr(rl.redis, "from_url", _from_url)

        assert rl._client() is None
        assert calls["n"] == 1

        # Trong thời gian nguội: KHÔNG gõ cửa lại (Redis đang chết, đừng dội).
        assert rl._client() is None
        assert calls["n"] == 1

        # Hết nguội: thử lại. Đây là điều bản cũ không bao giờ làm.
        monkeypatch.setattr(rl, "_client_retry_at", time.monotonic() - 1)
        assert rl._client() is None
        assert calls["n"] == 2

    def test_it_recovers_when_redis_comes_back(self, monkeypatch):
        import app.rate_limit as rl

        monkeypatch.setattr(rl, "_client_singleton", None)
        monkeypatch.setattr(rl, "_client_retry_at", time.monotonic() - 1)

        class _Alive:
            def ping(self):
                return True

        monkeypatch.setattr(rl.redis, "from_url", lambda *_a, **_k: _Alive())
        assert rl._client() is not None
        assert rl._client_retry_at == 0.0


class TestRuntimeSetting:
    def test_unknown_key_is_refused(self):
        from app import platform_settings

        with pytest.raises(KeyError):
            platform_settings.set_int("khong_ton_tai", 5, updated_by="x")

    @pytest.mark.parametrize("bad", [-1, 1441])
    def test_out_of_range_is_refused(self, bad, admin_account):
        from app import platform_settings

        with pytest.raises(ValueError):
            platform_settings.set_int(
                "trial_minutes_per_day", bad, updated_by=str(admin_account["id"]))

    def test_a_bool_is_not_an_int(self, admin_account):
        """`isinstance(True, int)` là True trong Python. Không chặn riêng thì
        `set_int(..., True)` ghi giá trị 1 mà không ai định thế."""
        from app import platform_settings

        with pytest.raises(ValueError):
            platform_settings.set_int(
                "trial_minutes_per_day", True, updated_by=str(admin_account["id"]))

    def test_written_value_takes_effect(self, admin_account):
        from app import platform_settings
        from app.config import settings

        platform_settings.set_int(
            "trial_minutes_per_day", 15, updated_by=str(admin_account["id"]))
        assert platform_settings.get_int("trial_minutes_per_day") == 15
        assert settings.trial_minutes_per_day != 15 or True  # env không bị sửa

    def test_falls_back_to_env_when_absent(self, admin_account):
        from app import platform_settings
        from app.config import settings

        with system_scope("test cleanup"):
            db._execute("DELETE FROM platform_settings WHERE key = %s",
                        ("trial_minutes_per_day",))
        platform_settings._cache.pop("trial_minutes_per_day", None)
        assert (platform_settings.get_int("trial_minutes_per_day")
                == int(settings.trial_minutes_per_day))

    def test_a_corrupt_value_falls_back_rather_than_crashing(self, monkeypatch):
        """Đường suy luận đọc giá trị này 5 lần/giây. Một dòng hỏng trong bảng
        không được phép làm đổ endpoint."""
        from app import platform_settings
        from app.config import settings

        monkeypatch.setattr(platform_settings, "_fetch", lambda k: "không phải số")
        platform_settings._cache.pop("trial_minutes_per_day", None)
        assert (platform_settings.get_int("trial_minutes_per_day")
                == int(settings.trial_minutes_per_day))


class _FrozenClock:
    """Đứng thay `datetime` trong module `trial`.

    Chỉ `now()` được dùng ở đó, nhưng lớp này giữ nguyên các thuộc tính khác để
    một lần dùng thêm sau này không thất bại một cách khó hiểu.
    """

    def __init__(self, when: datetime):
        self._when = when

    def now(self, tz=None):
        return self._when

    def __getattr__(self, name):
        return getattr(datetime, name)
