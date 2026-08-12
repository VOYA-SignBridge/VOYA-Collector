"""A task dispatched by one tenant must run as that tenant, not as the platform.

Before this, every Celery task ran in system scope regardless of who triggered
it. That was a deliberate simplification, not an accident — the tenant of a row
a maintenance job writes comes from the row, and beat schedules have no tenant
at all. But it meant a task dispatched from inside a tenant request lost the
scope on the way to the worker, and any read it did saw every tenant's rows.

Three properties are worth pinning, and only the first is obvious:

  * a tenant scope survives the trip through the broker
  * platform work still gets system scope, because it has no header to carry
  * a header can only NARROW the scope — there is no value it can carry that
    grants system scope, since system is what you get by *failing* to be a
    valid tenant

The publish half is tested against a real broker rather than by calling the
handler directly. Calling the function proves the function; publishing proves
it is actually connected to the signal, which is the half that silently breaks.
"""

from __future__ import annotations

import json

import pytest

from app.tenant_context import (
    clear_scope, current_tenant, describe_scope, in_system_scope,
    no_scope, system_scope, tenant_scope,
)
from app.worker import (
    TENANT_HEADER, clear_structlog_context, setup_structlog_context,
    stamp_tenant_on_task,
)

#: A Redis db used by nothing else. Not 0 (production traffic) and not 15
#: (the rate-limit namespace the rest of the suite uses).
PROBE_BROKER = "redis://redis:6379/14"
#: With the Redis transport the queue name IS the list key. Naming an
#: undeclared queue silently publishes nowhere — the first version of this file
#: used "voya_tenant_probe" and read back None every time. Isolation comes from
#: db 14, which nothing else in the stack touches, not from the queue name.
PROBE_QUEUE = "celery"


@pytest.fixture
def published(monkeypatch):
    """Publish a real message and hand back the raw envelope from the broker.

    A dedicated Celery app on a scratch broker, NOT the production one. Two
    reasons: reassigning `celery_app.conf.broker_url` after the app has built a
    connection does not move the publish (the first version of this fixture did
    exactly that and silently posted to the live broker), and a message on a
    real queue could be picked up and executed by the running worker.

    Using a separate app does not weaken the test. `before_task_publish` is a
    GLOBAL signal, not one bound to an app — importing `app.worker` is what
    connects the handler, and any publish then exercises it. That is precisely
    the wiring worth proving: a handler defined but never connected is the
    failure this catches, and calling the function directly would not.
    """
    import redis
    from celery import Celery

    import app.worker  # noqa: F401  — the import is what connects the handler

    # `CELERY_BROKER_URL` in the environment OUTRANKS both the `Celery(broker=)`
    # constructor argument and a later `conf.update(broker_url=...)`. Both were
    # tried; both published to db 15 — the db this suite's rate-limit counters
    # live in — while the probe read db 14 and saw nothing. The symptom was an
    # empty queue, never an error. Removing the variable is the only thing that
    # actually moves the publish.
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)

    r = redis.Redis.from_url(PROBE_BROKER)
    probe_app = Celery("tenant_probe")
    probe_app.conf.update(
        broker_url=PROBE_BROKER, result_backend=PROBE_BROKER,
        task_serializer="json", accept_content=["json"],
    )
    # Asserted, not assumed. Publishing to the real broker would put messages a
    # live worker could execute, and this test would still pass.
    assert probe_app.conf.broker_url == PROBE_BROKER, "probe would hit the real broker"

    def _publish():
        r.delete(PROBE_QUEUE)
        probe_app.send_task("probe.noop", queue=PROBE_QUEUE)
        raw = r.lpop(PROBE_QUEUE)
        assert raw is not None, "nothing was published"
        return json.loads(raw)["headers"]

    try:
        yield _publish
    finally:
        r.delete(PROBE_QUEUE)


class _FakeRequest:
    """Stands in for `task.request`, which is a `celery.app.task.Context`.

    Verified against the real thing: a key set in `before_task_publish`'s
    `headers` dict reaches the worker and `Context(headers)` exposes it as an
    attribute. `getattr(..., default)` is the access pattern under test, so a
    plain object with or without the attribute reproduces both branches
    exactly.
    """

    def __init__(self, **attrs):
        self.__dict__.update(attrs)


class _FakeTask:
    def __init__(self, name="app.tasks.example", **request_attrs):
        self.name = name
        self.request = _FakeRequest(**request_attrs)


@pytest.fixture(autouse=True)
def _reset_scope():
    yield
    clear_scope()


class TestDispatchStampsTheTenant:
    def test_a_tenant_scope_is_carried_into_the_message(self, published):
        with tenant_scope("truong-b"):
            headers = published()
        assert headers.get(TENANT_HEADER) == "truong-b"

    def test_platform_work_carries_no_tenant_header(self, published):
        """Beat schedules, the CLI and the startup sync run in system scope.
        Stamping them would pin genuinely cross-tenant work to one tenant."""
        with system_scope("test: platform work has no tenant"):
            headers = published()
        assert TENANT_HEADER not in headers

    def test_unscoped_dispatch_carries_no_tenant_header(self, published):
        with no_scope():
            headers = published()
        assert TENANT_HEADER not in headers

    def test_the_handler_tolerates_a_missing_headers_dict(self):
        """Celery calls this signal for every protocol; a handler that assumes
        protocol 2's shape would break dispatch itself, not just the tenant."""
        with tenant_scope("truong-b"):
            stamp_tenant_on_task(headers=None)  # must not raise


class TestTheWorkerAdoptsTheTenant:
    def test_a_stamped_task_runs_as_that_tenant(self):
        task = _FakeTask(**{TENANT_HEADER: "truong-b"})
        setup_structlog_context(task_id="t-1", task=task)
        assert current_tenant() == "truong-b"
        assert in_system_scope() is False

    def test_an_unstamped_task_still_runs_as_the_platform(self):
        """The behaviour every existing task has. A regression here turns every
        beat job into a job that sees zero rows and reports success."""
        setup_structlog_context(task_id="t-2", task=_FakeTask())
        assert in_system_scope() is True
        assert current_tenant() is None

    @pytest.mark.parametrize("bad", ["", "  ", "Truong B", "tenant\n", "a" * 200])
    def test_a_malformed_tenant_falls_back_to_the_platform(self, bad):
        """Not an exception: refusing to start a maintenance job because a
        header was mangled fails it closed on an unrelated detail. Falling back
        is precisely the behaviour the task had before the header existed.

        What must NOT happen is the bad value reaching the GUC, where it would
        behave as an empty partition and read as data loss.
        """
        task = _FakeTask(**{TENANT_HEADER: bad})
        setup_structlog_context(task_id="t-3", task=task)
        assert in_system_scope() is True
        assert current_tenant() is None

    @pytest.mark.parametrize("attempt,expected", [
        # Well-formed, so honoured — as an ORDINARY tenant with that name, not
        # as the platform. A tenant called "system" matches rows whose
        # tenant_id is the string "system", which is almost certainly none.
        ("system", "tenant:system"),
        ("all", "tenant:all"),
        # Uppercase is REFUSED, not lowercased. `is_valid_tenant_id` is strict
        # here on purpose: an id that differs only in case would become a
        # partition of its own, matching no rows while being indistinguishable
        # from the real tenant in every log line.
        ("SYSTEM", "system"),
        # Malformed, so refused, so the platform fallback.
        ("*", "system"),
        ("%", "system"),
    ])
    def test_no_header_value_grants_platform_access(self, attempt, expected):
        """The guarantee is structural, not a blocklist.

        System scope is reached only by `enter_system_scope`, which this path
        calls when there is NO usable tenant. No string routes to it, so there
        is no string anyone has to remember to filter — including the ones that
        look like they should mean "everything".
        """
        task = _FakeTask(**{TENANT_HEADER: attempt})
        setup_structlog_context(task_id="t-4", task=task)
        assert describe_scope() == expected

    def test_a_platform_wide_task_ignores_the_header(self):
        task = _FakeTask(name="app.export_tasks.example",
                         **{TENANT_HEADER: "truong-b"})
        task.platform_wide = True
        setup_structlog_context(task_id="t-6", task=task)
        assert in_system_scope() is True
        assert current_tenant() is None

    def test_postrun_clears_the_scope(self):
        """A prefork child is reused. A task that ends still holding a tenant
        would hand it to whatever the child picks up next."""
        task = _FakeTask(**{TENANT_HEADER: "truong-b"})
        setup_structlog_context(task_id="t-5", task=task)
        clear_structlog_context()
        assert describe_scope() == "unscoped"


class TestTheAggregateTasksStayPlatformWide:
    """The tasks that build ONE artifact from every tenant's rows.

    This list is the part of the design a future change is most likely to break
    — not by editing it, but by adding a sixth aggregate task and not thinking
    about scope. The names are spelled out rather than discovered, so adding one
    is a deliberate act with a test to update.

    The cost of getting it wrong is asymmetric and quiet: a scoped export
    succeeds and publishes a spreadsheet that is simply missing rows.
    """

    EXPECTED = {
        "app.export_tasks.export_samples_to_sheets",
        "app.export_tasks.export_labels_to_sheets",
        "app.export_tasks.mirror_catalog_csvs_to_drive",
        "app.export_tasks.reconcile_samples_csv_task",
        "app.sync_tasks.download_missing_files_to_local",
        "app.training_tasks.cleanup_training_artifacts",
        # --- mặt phẳng SaaS (v4) ---
        # Gộp số đo và giao webhook đều đi qua NHIỀU tenant trong một lượt
        # chạy; bị giới hạn vào ngữ cảnh của người phái thì chúng chỉ làm được
        # một phần và không báo lỗi — đúng kiểu hỏng mà export_tasks đã ghi lại
        # ("the export succeeds, it is just short").
        "app.saas_tasks.rollup_usage_daily",
        "app.saas_tasks.deliver_webhooks",
        "app.saas_tasks.cleanup_saas_artifacts",
        # Chỉ chạm MỘT tenant, nhưng được phái từ một quản trị viên nền tảng
        # đứng ở tenant KHÁC với tenant được xuất — đúng tình huống mà ngữ cảnh
        # của người phái là câu trả lời sai.
        "app.saas_tasks.run_tenant_export",
        # Lượt quét vòng đời đăng ký. Nó phải xét MỌI tenant — đó chính là công
        # việc của nó, và một lượt quét chỉ thấy tenant của người phái là một
        # lượt quét vô nghĩa. Hơn nữa nó do celery-beat phái, nơi không có
        # người dùng nào để lấy ngữ cảnh.
        "app.saas_tasks.sweep_subscriptions",
        # `refresh_tokens` thuộc mặt phẳng DANH TÍNH — bảng không mang
        # `tenant_id`. Một lượt dọn bị giới hạn theo tenant sẽ không xoá được gì
        # và cũng không báo lỗi, vì RLS lọc hết chứ không từ chối.
        "app.saas_tasks.cleanup_refresh_tokens",
        # Quét tồn đọng hỗ trợ: nó đọc phiếu của MỌI tổ chức để biết tổ chức nào
        # đang có phiếu bị bỏ quên, và nó do celery-beat phái nên không có người
        # dùng nào để lấy ngữ cảnh. Bị giới hạn theo tenant thì RLS trả về 0
        # dòng và lượt quét báo "không có tồn đọng" một cách hoàn hảo, mãi mãi —
        # tức là hỏng đúng theo cái kiểu mà chính nó sinh ra để chống.
        "app.saas_tasks.sweep_support_backlog",
        # Gửi thư báo phiếu mới. Nó tự tra danh sách người nhận theo `tenant_id`
        # được truyền vào, nên nó phải đọc `users` NGOÀI phạm vi của người phái
        # — người phái là người dùng vừa mở phiếu, không phải quản trị viên.
        "app.saas_tasks.send_support_ticket_emails",
    }

    def test_exactly_these_tasks_are_platform_wide(self):
        from app.worker import celery_app

        import app.export_tasks  # noqa: F401
        import app.saas_tasks  # noqa: F401
        import app.sync_tasks  # noqa: F401
        import app.training_tasks  # noqa: F401

        found = {
            name for name, task in celery_app.tasks.items()
            if getattr(task, "platform_wide", False)
        }
        assert found == self.EXPECTED

    def test_the_flag_survives_celery_task_construction(self):
        """`@celery_app.task(platform_wide=True)` relies on Celery turning an
        unknown option into a class attribute. That is real but undocumented
        behaviour, so it is measured rather than assumed — if a Celery upgrade
        drops it, every one of these silently becomes tenant-scoped."""
        from app.export_tasks import export_samples_to_sheets

        assert export_samples_to_sheets.platform_wide is True
