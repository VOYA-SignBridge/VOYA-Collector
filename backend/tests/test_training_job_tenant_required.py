"""C2a — `training_jobs.tenant_id` phải tường minh, không suy ra.

Chạy:
    bash scripts/run_tests.sh backend/tests/test_training_job_tenant_required.py -v -s

Bất biến
========
```
CreateTrainingJob(thiếu tenant)      ->  TỪ CHỐI
CreateTrainingJob(tenant='default')  ->  hợp lệ, nếu nghiệp vụ thật sự nhắm default
```

Cùng khuôn đã chứng minh ở B1 cho `users.tenant_id`. Ở đây hậu quả nặng hơn một
bậc: một job lập hồ sơ thiếu tenant không chỉ thuộc nhầm tổ chức mà kéo theo mọi
thứ móc vào nó — hợp đồng lớp đầu ra, hiện vật, sự kiện webhook.

Hai tầng phải cùng đóng
=======================
Bỏ DEFAULT ở CSDL mà để nguyên phép rơi-về-default trong Python thì không đổi
được gì: `upsert_training_job` sẽ vẫn điền `'default'` trước khi câu lệnh chạy
tới PostgreSQL. Trước 16/08/2026 nó rơi ở **cả hai** nhánh:

```
system scope   ->  row.tenant  or DEFAULT_TENANT_ID
request scope  ->  ambient_tenant()  (= current_tenant() or DEFAULT_TENANT_ID)
```

Nên các ca dưới đây kiểm cả lược đồ lẫn hàm.

Điều KHÔNG đổi
==============
Job đang mang `tenant_id='default'` vẫn thuộc `default`. Migration không di
chuyển hàng nào — nó chỉ chặn việc tạo THÊM một job thuộc tenant khởi tạo do sơ
suất.
"""

from __future__ import annotations

import uuid

import pytest

from app.storage.metadata_db import _migration_cursor, upsert_training_job
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import TenantScopeError, no_scope, system_scope, tenant_scope


def _doc_tenant(job_id: str):
    """Đọc dưới sentinel hệ thống, KHÔNG dưới phạm vi một tenant.

    `training_jobs` nằm dưới RLS + FORCE, nên chủ sở hữu lược đồ cũng bị lọc.
    Một truy vấn không có phạm vi khớp 0 dòng — và 0 dòng đọc thành "không có
    gì", tức phép kiểm sẽ báo sai. Phép đo phải nhìn thấy hàng THẬT SỰ mang giá
    trị gì, kể cả khi nó vừa bị ghi sang tenant khác.
    """
    with _migration_cursor() as cur:
        cur.execute("SELECT set_config('app.system_scope','on',false)")
        cur.execute("SELECT tenant_id FROM training_jobs WHERE job_id = %s", (job_id,))
        r = cur.fetchone()
    return r[0] if r else None


def _xoa(job_id: str) -> None:
    with _migration_cursor() as cur:
        cur.execute("SELECT set_config('app.system_scope','on',false)")
        cur.execute("DELETE FROM training_jobs WHERE job_id = %s", (job_id,))


def _job(tenant=None) -> dict:
    row = {
        "job_id": str(uuid.uuid4()), "status": "queued", "model_type": "tcn",
        "config": {}, "auth_user_id": None, "created_at": None,
        "started_at": None, "completed_at": None, "current_epoch": 0,
        "total_epochs": 1, "checkpoint_path": None, "test_acc": None,
        "test_f1": None, "error_message": None, "promoted_at": None,
    }
    if tenant is not None:
        row["tenant_id"] = tenant
    return row


# =========================================================================
# C2a-3 — lược đồ tự nó phải từ chối
# =========================================================================

def test_C2a_3_INSERT_thieu_tenant_bi_CSDL_tu_choi():
    """Bỏ `tenant_id` khỏi câu INSERT phải NỔ, không sinh ra job `default`."""
    jid = str(uuid.uuid4())
    with pytest.raises(Exception) as ei:
        with _migration_cursor() as cur:
            cur.execute(
                "INSERT INTO training_jobs (job_id, status, model_type) "
                "VALUES (%s, 'queued', 'tcn')", (jid,))
    print(f"\n[evidence] CSDL tu choi: {type(ei.value).__name__}")

    with _migration_cursor() as cur:
        cur.execute("SELECT count(*) FROM training_jobs WHERE job_id = %s", (jid,))
        assert cur.fetchone()[0] == 0


def test_luoc_do_giu_NOT_NULL_va_bo_DEFAULT():
    with _migration_cursor() as cur:
        cur.execute(
            "SELECT is_nullable, column_default FROM information_schema.columns "
            "WHERE table_name = 'training_jobs' AND column_name = 'tenant_id'")
        is_nullable, default = cur.fetchone()
    print(f"\n[evidence] is_nullable={is_nullable} column_default={default!r}")
    assert is_nullable == "NO"
    assert default is None


# =========================================================================
# C2a-5 — hàm không có mặc định trong Python
# =========================================================================

def test_C2a_5_system_scope_thieu_tenant_thi_NO_chu_khong_doan():
    """Tác vụ nền: tenant phải đi theo CHÍNH HÀNG job.

    Đây là nhánh của Celery. Trước bản vá nó là
    `row.tenant or DEFAULT_TENANT_ID`, nên một job mất tenant được lập hồ sơ
    dưới tenant khởi tạo — im lặng.
    """
    with system_scope("test: tac vu nen lap ho so job"):
        with pytest.raises(ValueError) as ei:
            upsert_training_job(_job())
    print(f"\n[evidence] {ei.value}")
    assert "default" in str(ei.value).lower()


def test_C2a_5_request_scope_khong_co_tenant_thi_NO():
    """Đường request: `require_tenant()` ném lỗi, khác `ambient_tenant()`.

    `ambient_tenant()` trả `default` khi không có phạm vi — đúng với đường GHI
    hàng dữ liệu có trước khi tenant tồn tại, sai với việc lập hồ sơ một job.
    """
    with no_scope():
        with pytest.raises(TenantScopeError):
            upsert_training_job(_job())


@pytest.mark.parametrize("gia_tri", ["", "   "])
def test_gia_tri_rong_trong_hang_khong_thanh_default(gia_tri):
    with system_scope("test: hang job mang tenant rong"):
        with pytest.raises(ValueError):
            upsert_training_job(_job(gia_tri))


# =========================================================================
# C2a-1 / C2a-2 — giá trị TƯỜNG MINH đi qua nguyên vẹn
# =========================================================================

@pytest.mark.parametrize("tenant", ["iso_a", DEFAULT_TENANT_ID])
def test_C2a_1_2_tenant_tuong_minh_duoc_giu_nguyen(tenant):
    """`default` KHÔNG phải giá trị đáng ngờ — nó chỉ đáng ngờ khi không ai gán.

    Ca `default` là ca dễ bỏ sót nhất: sửa quá tay thành "cấm default" sẽ chặn
    luôn đường bootstrap hợp lệ.
    """
    row = _job(tenant)
    with system_scope("test: lap ho so job voi tenant tuong minh"):
        upsert_training_job(row)
    luu = _doc_tenant(row["job_id"])
    print(f"\n[evidence] yeu cau={tenant!r} luu={luu!r}")
    assert luu == tenant
    _xoa(row["job_id"])


def test_duong_request_lap_ho_so_theo_pham_vi_dang_hanh_dong():
    """Người gọi KHÔNG tự khai tenant — nó lấy từ phạm vi request.

    Kể cả khi hàng job mang sẵn một tenant khác, phạm vi đang hành động mới là
    thứ quyết định. Đó là bất biến chống việc lập hồ sơ job dưới tổ chức khác.
    """
    row = _job("iso_b")                      # người gọi cố khai iso_b …
    with tenant_scope("iso_a"):              # … nhưng đang hành động cho iso_a
        upsert_training_job(row)
    luu = _doc_tenant(row["job_id"])
    print(f"\n[evidence] hang khai 'iso_b', pham vi 'iso_a' -> luu {luu!r}")
    assert luu == "iso_a"
    _xoa(row["job_id"])
