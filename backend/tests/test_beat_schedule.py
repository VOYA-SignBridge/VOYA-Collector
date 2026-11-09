"""Lịch định kỳ phải khớp bản đang chạy, và mọi task trong lịch phải có worker nhận.

Đợt tái cấu trúc tháng 10/2026 làm rơi 9 việc khỏi lịch (SaaS, đối soát
samples.csv, Lookup list) và để 3 module task ngoài danh sách nạp của worker.
Mọi test khác vẫn xanh vì không test nào hỏi celery-beat sẽ phái gì.
"""

from types import SimpleNamespace

from app.infrastructure.celery.schedules import build_beat_schedule

ALWAYS = {
    "app.training_tasks.cleanup_training_artifacts",
    "app.export_tasks.reconcile_samples_csv_task",
    "app.saas_tasks.rollup_usage_daily",
    "app.saas_tasks.deliver_webhooks",
    "app.saas_tasks.cleanup_saas_artifacts",
    "app.saas_tasks.cleanup_refresh_tokens",
    "app.saas_tasks.sweep_support_backlog",
    "app.saas_tasks.reconcile_storage_quota",
}
#: Đã thay bằng `sync_lookup_lists`; không được quay lại lịch.
RETIRED = {
    "app.export_tasks.export_samples_to_sheets",
    "app.export_tasks.export_labels_to_sheets",
    "app.export_tasks.mirror_catalog_csvs_to_drive",
}


def _tasks(**kw):
    s = SimpleNamespace(subscription_sweep_enabled=True, use_google_drive=True,
                        drive_pull_interval_hours=6)
    for k, v in kw.items():
        setattr(s, k, v)
    return {e["task"] for e in build_beat_schedule(s).values()}


def test_lich_co_du_viec_cua_ban_dang_chay():
    full = _tasks()
    assert ALWAYS <= full
    assert {"app.saas_tasks.sweep_subscriptions", "app.export_tasks.sync_lookup_lists",
            "app.sync_tasks.download_missing_files_to_local"} <= full
    assert ALWAYS == _tasks(subscription_sweep_enabled=False, use_google_drive=False)


def test_viec_da_thay_khong_quay_lai_lich():
    assert not (RETIRED & _tasks())


def test_moi_task_trong_lich_deu_co_worker_nhan():
    from app.worker import celery_app

    assert not (_tasks() - set(celery_app.tasks))


def test_task_xep_hang_bang_ten_cu_van_co_worker_nhan():
    from app.worker import celery_app

    for name in ("app.preview_tasks.render_session_preview_task",
                 "app.saas_tasks.run_tenant_export", "app.saas_tasks.run_personal_export",
                 "app.saas_tasks.send_support_ticket_emails"):
        assert name in celery_app.tasks, name


def test_celery_di_qua_duoc_redis_khoi_dong_lai():
    from app.worker import celery_app

    conf = celery_app.conf
    assert conf.broker_connection_retry and conf.broker_connection_retry_on_startup
    assert conf.broker_connection_max_retries is None
    assert conf.broker_transport_options["visibility_timeout"] == 3600
