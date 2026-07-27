"""Training failure classification + admin escalation (app/training_alerts)."""

from __future__ import annotations

import pytest

from app import training_alerts as ta


SYSTEM_MESSAGES = [
    "Không gửi được job tới trainer (Redis/Celery down?): redis down",
    "Không khởi động được training process: boom",
    "Quá thời gian tối đa 6h — job bị dừng tự động",
    "Training process thoát với mã lỗi 1 (xem run.log)",
    "CUDA out of memory",
    "Some unexpected internal traceback",  # unknown → system by default
]

DATA_MESSAGES = [
    "Không có dữ liệu: splits train.csv rỗng cho phương ngữ đã chọn",
    "dataset empty, no samples for label",
    "thiếu dữ liệu huấn luyện",
]


@pytest.mark.parametrize("msg", SYSTEM_MESSAGES)
def test_system_messages_classified_system(msg):
    assert ta.classify_training_error(msg) == ta.SYSTEM
    assert ta.is_system_failure(msg) is True


@pytest.mark.parametrize("msg", DATA_MESSAGES)
def test_data_messages_classified_data(msg):
    assert ta.classify_training_error(msg) == ta.DATA
    assert ta.is_system_failure(msg) is False


def test_notify_returns_true_and_increments_counter_for_system(monkeypatch):
    from app.metrics import training_system_failures_total

    before = training_system_failures_total.labels(source="dispatch")._value.get()
    escalated = ta.notify_admins_training_failure(
        job_id="job-x", actor="alice", error="redis down", source="dispatch"
    )
    after = training_system_failures_total.labels(source="dispatch")._value.get()

    assert escalated is True
    assert after == before + 1


def test_notify_is_noop_for_data_failure():
    escalated = ta.notify_admins_training_failure(
        job_id="job-y", actor="bob",
        error="Không có dữ liệu: splits rỗng", source="trainer_exit",
    )
    assert escalated is False
