"""Gieo đúng một job đã hoàn thành cho `iso_a`. Chỉ chạy trên CSDL tạm.

Tài khoản dùng lại `iso_user_a`, `iso_user_b` của `seed_isolation_fixture.py`.
Checkpoint là bản thật đang phục vụ `hoa-de`, nên dịch vụ realtime nạp nó thật.
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.storage.metadata_db import _cursor, _fetch_all, insert_training_metric, upsert_training_job
from app.modules.saas.tenant_context import system_scope, tenant_scope

CSDL = "signdb_pytest_e2e"
TENANT = "iso_a"
PHUONG_NGU = "hoa-de"
CONFIG = Path("/workspace/backend/realtime_service/config")
CHECKPOINTS = Path("/workspace/checkpoints")


def main() -> None:
    with system_scope("kiem thu: xac nhan dich"):
        ten = _fetch_all("SELECT current_database() AS d")[0]["d"]
        chu = _fetch_all("SELECT id FROM users WHERE username = 'iso_user_a'")
        quan_tri = _fetch_all("SELECT id FROM users WHERE username = 'iso_admin_a'")
    if ten != CSDL:
        sys.exit(f"TU CHOI: dang tro vao '{ten}', chi duoc gieo tren '{CSDL}'.")

    # `golden-path.spec.ts` đăng nhập bằng quản trị viên và làm việc ở tổ chức có dữ liệu.
    with system_scope("kiem thu: dat noi lam viec"):
        with _cursor() as cur:
            cur.execute("UPDATE users SET active_tenant_id = 'default' WHERE username = 'iso_admin_a'")

    mo_hinh = next(m for m in json.loads((CONFIG / "models.json").read_text(encoding="utf-8"))["models"]
                   if m["dialect"] == PHUONG_NGU)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    bay_gio = datetime.now(timezone.utc).isoformat()

    def gieo_job(tenant: str, nguoi: str) -> str:
        job_id = str(uuid.uuid4())[:8]
        tep = CHECKPOINTS / f"{job_id}.pt"
        shutil.copyfile(CONFIG / mo_hinh["checkpoint_path"], tep)
        with tenant_scope(tenant):
            upsert_training_job({
                "job_id": job_id, "status": "completed", "model_type": "hdgcn",
                "config": {"model_type": "hdgcn", "dialects": [PHUONG_NGU], "languages": ["vn"]},
                "auth_user_id": nguoi, "created_at": bay_gio, "started_at": bay_gio,
                "completed_at": bay_gio, "current_epoch": 1, "total_epochs": 1,
                "checkpoint_path": str(tep), "test_acc": 0.9, "test_f1": 0.9,
                "error_message": None, "promoted_at": None,
            })
            # Trang kết quả chỉ dựng khi job có chỉ số, như mọi job huấn luyện thật.
            insert_training_metric({"job_id": job_id, "epoch": 1, "train_loss": 0.4, "train_acc": 0.9,
                                    "val_loss": 0.5, "val_acc": 0.9, "val_f1": 0.9})
        return job_id

    job_id = gieo_job(TENANT, str(chu[0]["id"]))
    # Job của người khác ở `default`: job riêng của thành viên không ai khác thấy được,
    # nên ca "không promote được model của người khác" cần một job thường có sẵn.
    gieo_job("default", str(quan_tri[0]["id"]))
    print(json.dumps({"job": job_id, "tenant": TENANT}))


if __name__ == "__main__":
    main()
