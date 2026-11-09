"""Lịch chạy định kỳ (celery-beat).

Giữ ĐÚNG như bản đang chạy trên máy thật. Đợt tái cấu trúc từng dựng tệp này từ
một bản `worker.py` cũ: mất 9 việc (SaaS, đối soát samples.csv, Lookup list) và
bật lại 3 việc đã bị thay (xuất Sheet mỗi 30/60 giây, chép CSV lên Drive mỗi 5
phút). `tests/test_beat_schedule.py` canh để chuyện đó không lặp lại.

Tên task là tên CŨ (`app.saas_tasks.*`, `app.export_tasks.*`): beat phái bằng
chuỗi, và tin nhắn đã xếp hàng trước lần cập nhật cũng mang tên cũ.
"""

from __future__ import annotations

import os
from typing import Any, Dict

DAY = 86400.0
HOUR = 3600.0


def build_beat_schedule(settings) -> Dict[str, Dict[str, Any]]:
    schedule: Dict[str, Dict[str, Any]] = {
        # Dọn checkpoint thử nghiệm và log job cũ.
        "cleanup-training-artifacts-daily": {
            "task": "app.training_tasks.cleanup_training_artifacts", "schedule": DAY},
        # Lưới an toàn: thêm lại mẫu đang hoạt động trong Postgres mà samples.csv
        # thiếu (chỉ thêm; vá cuộc đua append và ghi lại danh mục).
        "reconcile-samples-csv-every-5min": {
            "task": "app.export_tasks.reconcile_samples_csv_task", "schedule": 300.0},
        # --- mặt phẳng SaaS ---
        # Gộp số đo theo ngày nhưng chạy mỗi giờ để bảng điều khiển thấy hôm nay.
        "rollup-usage-hourly": {
            "task": "app.saas_tasks.rollup_usage_daily", "schedule": HOUR},
        # Độ trễ tối đa của một webhook; lần thử lại đầu cũng cách một phút.
        "deliver-webhooks-every-minute": {
            "task": "app.saas_tasks.deliver_webhooks", "schedule": 60.0},
        "cleanup-saas-artifacts-daily": {
            "task": "app.saas_tasks.cleanup_saas_artifacts", "schedule": DAY},
        # refresh_tokens chỉ lớn lên nếu không ai dọn.
        "cleanup-refresh-tokens-daily": {
            "task": "app.saas_tasks.cleanup_refresh_tokens", "schedule": DAY},
        # Cảnh báo "phiếu chờ quá 5 giờ" cần độ trễ phát hiện nhỏ hơn hẳn 5 giờ.
        "support-backlog-every-30min": {
            "task": "app.saas_tasks.sweep_support_backlog", "schedule": 1800.0},
        # Đối chiếu bộ đếm dung lượng với cây tệp thật; đi bộ mọi tenant nên mỗi ngày.
        "reconcile-storage-quota-daily": {
            "task": "app.saas_tasks.reconcile_storage_quota", "schedule": DAY},
    }

    # Vòng đời đăng ký (nhắc hạn, ân hạn, khoá mềm). Mỗi giờ để một lần worker
    # khởi động lại không làm lỡ nguyên một ngày.
    if settings.subscription_sweep_enabled:
        schedule["subscription-sweep-hourly"] = {
            "task": "app.saas_tasks.sweep_subscriptions", "schedule": HOUR}

    # Sheet Lookup list theo tổ chức, thay cho xuất Sheet 30/60 giây và chép CSV
    # lên Drive 5 phút một lần. Tự dừng ngay khi dấu vân tay không đổi.
    if settings.use_google_drive:
        schedule["sync-lookup-lists"] = {
            "task": "app.export_tasks.sync_lookup_lists",
            "schedule": float(os.getenv("LOOKUP_LIST_INTERVAL_SECONDS", "300"))}

    # Kéo về tệp có trong DB mà thiếu trên đĩa. Tắt mặc định.
    if settings.use_google_drive and int(getattr(settings, "drive_pull_interval_hours", 0)) > 0:
        schedule["pull-missing-files-from-drive"] = {
            "task": "app.sync_tasks.download_missing_files_to_local",
            "schedule": float(settings.drive_pull_interval_hours) * HOUR}
    return schedule
