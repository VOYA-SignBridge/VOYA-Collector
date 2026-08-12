"""Nhật ký kiểm toán: che bí mật, không bao giờ làm hỏng hành động đang ghi.

Tách từ `test_schema_v3.py` (593 dòng, bốn mối quan tâm không liên quan gộp
chung). Bối cảnh đầy đủ của đợt vá lược đồ: `docs/needFix/SAAS_SCHEMA_DESIGN.md`
§9sexies.
"""

from __future__ import annotations

import uuid

import pytest

from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()

# ------------------------------------------------------------------ audit

def test_audit_redacts_secrets():
    """Người dùng đặt ra quy tắc và nó không có ngoại lệ: không log mã quan
    trọng. `detail` là JSONB tự do nên nó là chỗ dễ rò nhất."""
    from app import audit

    cleaned = audit._redact({
        "password": "@Minh123456",
        "otp": "123456",
        "X-Auth-Token": "abc",
        "nested": {"user_password": "x", "ten": "giữ lại"},
        "danh_sach": [{"api_key": "k"}],
        "vo_hai": 30,
    })
    assert cleaned["password"] == audit._REDACTED
    assert cleaned["otp"] == audit._REDACTED
    assert cleaned["X-Auth-Token"] == audit._REDACTED
    assert cleaned["nested"]["user_password"] == audit._REDACTED
    assert cleaned["nested"]["ten"] == "giữ lại"
    assert cleaned["danh_sach"][0]["api_key"] == audit._REDACTED
    assert cleaned["vo_hai"] == 30


def test_audit_redaction_stops_recursing():
    """Đệ quy không giới hạn trên dữ liệu do người gọi đưa vào là một cách tự
    treo mình."""
    from app import audit

    deep: dict = {"a": {}}
    node = deep["a"]
    for _ in range(50):
        node["a"] = {}
        node = node["a"]
    audit._redact(deep)  # không được ném, không được treo


def test_audit_never_raises_when_the_write_fails(monkeypatch):
    """Xem docstring `app/audit.py`: kiểm toán không được là điểm chết của hệ
    thống. Một trục trặc Postgres không được biến mọi hành động quản trị thành
    lỗi 500."""
    from app import audit

    def boom(**_kwargs):
        raise RuntimeError("postgres đang chết")

    monkeypatch.setattr(db, "insert_audit_log", boom)
    assert audit.record("thu.nghiem") is False


def test_audit_writes_and_reads_back():
    from app import audit
    from app.tenant_context import system_scope

    action = f"test.schema_v3.{uuid.uuid4().hex[:8]}"
    with system_scope("test: ghi và đọc lại một dòng kiểm toán"):
        assert audit.record(action, detail={"password": "bi mat", "so": 1}) is True
        rows = db.list_audit_log(limit=50, action_prefix="test.schema_v3.")
        mine = [r for r in rows if r["action"] == action]
        assert len(mine) == 1
        assert mine[0]["detail"]["password"] == audit._REDACTED
        assert mine[0]["detail"]["so"] == 1
        db._execute("DELETE FROM audit_log WHERE action = %s", (action,))


def test_audit_rejects_a_blank_action():
    from app import audit

    assert audit.record("") is False


def test_audit_writes_a_platform_row_in_system_scope():
    """Sự kiện tầng nền tảng — `tenant_id` NULL — ghi được, nhưng CHỈ trong
    system scope.

    `audit_log` là bảng duy nhất cho phép `tenant_id` NULL. Nó vẫn chịu vị từ
    RLS dùng chung, nên một dòng NULL chỉ qua được WITH CHECK khi
    `app.system_scope = 'on'`. Đây là đường mà Celery beat và các CLI đi.
    """
    from app import audit

    action = f"test.platform.{uuid.uuid4().hex[:8]}"
    with system_scope("test: ghi sự kiện tầng nền tảng"):
        assert audit.record(action, detail={"nguon": "beat"}) is True
        rows = db.list_audit_log(limit=50, action_prefix="test.platform.")
        mine = [r for r in rows if r["action"] == action]
        assert len(mine) == 1
        assert mine[0]["tenant_id"] is None
        db._execute("DELETE FROM audit_log WHERE action = %s", (action,))


def test_audit_fails_closed_when_there_is_no_scope_at_all():
    """Ngoài MỌI phạm vi, dòng kiểm toán KHÔNG ghi được — và như thế là đúng.

    Vị từ RLS ngoài mọi phạm vi cho ra: `'' = 'on'` là false, `NULL = ''` là
    NULL, `false OR NULL` là NULL — không phải TRUE, nên WITH CHECK từ chối.
    Fail-closed, đúng thiết kế ở `storage/rls.py`.

    Hai điều test này ghim, và điều thứ hai mới là lý do nó tồn tại:

    1. `record()` **nuốt** lỗi đó và trả False thay vì ném 500 lên người dùng.
    2. Docstring của `record()` từng hứa "không có phạm vi nào thì dòng được
       ghi ở tầng nền tảng". Lời hứa đó SAI, và nó nguy hiểm vì nghe hợp lý:
       ai đọc nó sẽ tin rằng một tác vụ nền không cần phạm vi vẫn để lại dấu
       vết, trong khi thực tế dấu vết đó bốc hơi cùng một dòng `[AUDIT-FAIL]`.

    Sản xuất không rơi vào đây: cả ba lối vào đều đặt phạm vi — middleware HTTP
    mỗi request, `task_prerun` mỗi tác vụ Celery (system scope khi không có
    header tenant), và `platform_command` mỗi lệnh CLI. Test này canh rằng nếu
    ai đó thêm lối vào THỨ TƯ mà quên đặt phạm vi, hành vi là mất dấu vết —
    để người viết bản vá đó đọc được hậu quả ở đây thay vì phát hiện trên
    sản xuất.

    Cả bộ test chạy trong system scope (`conftest._platform_scope`), nên phải
    bước ra bằng `no_scope()` — không có nó, test này xanh mà không kiểm gì.
    """
    from app import audit
    from app.tenant_context import in_system_scope, no_scope

    action = f"test.noscope.{uuid.uuid4().hex[:8]}"
    with no_scope():
        assert in_system_scope() is False
        assert audit.record(action) is False

    with system_scope("test: khẳng định không có dòng nào lọt"):
        rows = db.list_audit_log(limit=50, action_prefix="test.noscope.")
        assert [r for r in rows if r["action"] == action] == []


# --------------------------------------------- hai nhật ký, một lối ghi

def test_a_security_event_lands_in_the_durable_log_too():
    """`log_security_event` phải ghi CẢ HAI chỗ.

    Trước bản này nó chỉ đẩy vào danh sách Redis `sec:log` — cắt còn 500 mục,
    trên một Redis chạy `volatile-lru`. Bảy lối gọi (chặn IP, khoá tài khoản,
    ép đăng xuất...) chỉ tồn tại ở đó. Test này ghim rằng bản BỀN cũng nhận
    được, vì đó mới là bản trả lời được câu hỏi "tháng trước ai đã khoá tài
    khoản này".
    """
    from app import activity

    target = f"muc-tieu-{uuid.uuid4().hex[:8]}"
    activity.log_security_event("thu_nghiem", actor="nguoi-kiem-thu",
                                target=target, reason="ly do")

    with system_scope("test: đọc lại nhật ký bền"):
        rows = db.list_audit_log(limit=50, action_prefix="security.thu_nghiem")
        mine = [r for r in rows if r["target_id"] == target]
        assert len(mine) == 1, "sự kiện an ninh không xuống tới bảng bền"
        assert mine[0]["actor_label"] == "nguoi-kiem-thu"
        assert mine[0]["detail"]["reason"] == "ly do"
        db._execute("DELETE FROM audit_log WHERE target_id = %s", (target,))


def test_a_broken_durable_write_does_not_break_the_redis_write(monkeypatch):
    """Hai nhánh độc lập. Postgres chết không được làm mất luôn dòng Redis —
    nếu không thì thêm một nhật ký thứ hai lại làm YẾU đi cái thứ nhất."""
    from app import activity

    def boom(**_kwargs):
        raise RuntimeError("postgres đang chết")

    monkeypatch.setattr(db, "insert_audit_log", boom)

    target = f"muc-tieu-{uuid.uuid4().hex[:8]}"
    activity.log_security_event("thu_nghiem_hong", actor="ai-do", target=target)

    events = activity.list_security_log(limit=50)
    assert any(e.get("target") == target for e in events), \
        "nhánh Redis chết theo nhánh Postgres"




# ---------------------------------------------------------------------------
# Giám sát: sổ có còn lớn lên không, và lần ghi hỏng có ai biết không
#
# Hai kiểu hỏng, hai chỉ số, và chúng KHÔNG thay được nhau:
#
#   * ghi ném lỗi   → bộ đếm `voya_audit_write_failures_total`
#   * đường ghi biến mất, không ném gì → đồng hồ `voya_audit_log_age_seconds`
#
# Cái thứ hai mới là cái nguy hiểm: không ngoại lệ để đếm, không dòng log để
# đọc, chỉ có một cái sổ ngừng dày lên — trông hệt như một hệ thống yên tĩnh.
# ---------------------------------------------------------------------------


def test_a_failed_write_increments_the_prometheus_counter(monkeypatch):
    """`[AUDIT-FAIL]` cho tới nay chỉ nằm trong nhật ký ứng dụng, tức là chỉ
    tìm ra khi có người đi tìm. Một bộ đếm thì báo động được."""
    from app import audit
    from app.metrics import audit_write_failures_total

    def boom(**_kwargs):
        raise RuntimeError("postgres đang chết")

    monkeypatch.setattr(db, "insert_audit_log", boom)

    before = audit_write_failures_total._value.get()
    assert audit.record("thu.nghiem.dem") is False
    assert audit_write_failures_total._value.get() == before + 1


def test_a_broken_metrics_registry_does_not_break_the_write_path(monkeypatch):
    """Bộ đếm nằm TRÊN đường xử-lý-lỗi, nên nó phải là đoạn mã im lặng nhất
    trong tệp này.

    Nếu chính hệ đo lường ném lỗi ở đây, ngoại lệ đó thoát ra khỏi khối
    `except` của `record` và biến một lần ghi kiểm toán hỏng — thứ cả module
    này được thiết kế để KHÔNG làm ai chết — thành lỗi 500 ở đúng thao tác mà
    `record` đang cố ghi lại. Nói cách khác: lời phàn nàn tự nuốt mất chính nó.

    Hỏng ở tầng `inc()` chứ không thay cả `_count_failure`: bọc bảo vệ nằm bên
    TRONG hàm đó, nên thay cả hàm là bỏ qua đúng thứ đang cần kiểm.
    """
    from app import audit, metrics

    def boom(**_kwargs):
        raise RuntimeError("postgres đang chết")

    def registry_broken(*_a, **_kw):
        raise RuntimeError("registry chưa nạp")

    monkeypatch.setattr(db, "insert_audit_log", boom)
    monkeypatch.setattr(metrics.audit_write_failures_total, "inc", registry_broken)

    # Vẫn phải trả False, không được ném.
    assert audit.record("thu.nghiem.dem.hong") is False


def test_a_fresh_row_makes_the_age_gauge_small():
    from app import audit

    action = f"test.tuoi.{uuid.uuid4().hex[:8]}"
    with system_scope("test: ghi một dòng rồi đo tuổi"):
        assert audit.record(action) is True
    try:
        age = audit.seconds_since_last_entry()
        assert 0 <= age < 120, f"tuổi sổ ra {age}s ngay sau khi vừa ghi"
    finally:
        with system_scope("test cleanup"):
            db._execute("DELETE FROM audit_log WHERE action = %s", (action,))


def test_counting_recent_rows_sees_a_row_just_written():
    from app import audit

    action = f"test.dem.{uuid.uuid4().hex[:8]}"
    before = audit.count_since(3600)
    with system_scope("test: đếm dòng trong một giờ"):
        assert audit.record(action) is True
    try:
        assert audit.count_since(3600) >= before + 1
    finally:
        with system_scope("test cleanup"):
            db._execute("DELETE FROM audit_log WHERE action = %s", (action,))


def test_an_unreadable_table_reports_minus_one_not_zero(monkeypatch):
    """Ghim khoảng cách giữa "im lặng" và "không hỏi được".

    Trả 0 cho cả hai sẽ biến một sự cố kết nối thành cảnh báo "sổ ngừng tăng":
    đúng hồi chuông, sai lý do — và lần sau không ai tin nó nữa. Quy tắc cảnh
    báo trong `logging/alert-rules.yml` loại `-1` ra khỏi biểu thức, nên giá
    trị này là thứ giữ cho chuông không kêu bậy.
    """
    from app import audit
    from app.storage import metadata_db

    def boom(*_a, **_kw):
        raise RuntimeError("mất kết nối")

    monkeypatch.setattr(metadata_db, "_fetch_all", boom)

    assert audit.count_since(3600) == -1
    assert audit.seconds_since_last_entry() == -1.0


def test_the_metrics_endpoint_publishes_all_three_audit_signals():
    """Ba chỉ số phải CÓ MẶT trong đầu ra /metrics. Một quy tắc cảnh báo trỏ
    vào một chỉ số không tồn tại thì không kêu — nó chỉ đơn giản không bao giờ
    khớp, và Prometheus không phàn nàn gì cả."""
    from prometheus_client import generate_latest

    from app.metrics import _refresh_audit_gauges

    _refresh_audit_gauges()
    body = generate_latest().decode("utf-8")

    for name in ("voya_audit_write_failures_total",
                 "voya_audit_log_age_seconds",
                 "voya_audit_log_entries_1h"):
        assert name in body, f"{name} không có trong /metrics"
