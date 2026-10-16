"""C3 — đọc KHÔNG có phạm vi tenant thì RLS trả lời thế nào?

Chạy:
    bash scripts/run_tests.sh backend/tests/test_c3_ws_unscoped_read.py -q -s

Vì sao câu hỏi này quan trọng
=============================
`TenantScopeMiddleware.__call__` mở đầu bằng

```python
if scope["type"] != "http":
    await self.app(scope, receive, send)   # websocket + lifespan: KHÔNG đặt phạm vi
    return
```

Có chủ ý, và với `lifespan` thì đúng. Nhưng `routers/training.py` có một
endpoint **WebSocket** phát tiến độ huấn luyện, và nó gọi `_ensure_job_loaded`
rồi `list_training_metrics` — cùng những hàm mà đường HTTP dùng, chỉ khác là
chạy ngoài mọi phạm vi tenant.

Nên câu trả lời của RLS khi KHÔNG có phạm vi quyết định endpoint đó là kín hay
hở:

```
không phạm vi -> 0 dòng   ->  fail-CLOSED, WS không đọc được gì của ai
không phạm vi -> có dòng  ->  fail-OPEN,   WS là kênh đọc chéo mọi tổ chức
```

Đây là lần thứ tư trong đợt này câu hỏi "truy vấn chạy trước khi biết tenant"
xuất hiện. Ba lần trước đều ở mặt phẳng danh tính và đều fail-OPEN.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.storage.metadata_db import (  # noqa: E402
    _migration_cursor,
    get_training_job,
    list_training_metrics,
    upsert_training_job,
)
from app.tenant_context import no_scope, tenant_scope  # noqa: E402

A = "iso_a"
B = "iso_b"


@pytest.fixture
def job_cua_A():
    jid = str(uuid.uuid4())
    with tenant_scope(A):
        upsert_training_job({
            "job_id": jid, "status": "completed", "model_type": "tcn",
            "config": {}, "auth_user_id": None, "created_at": None,
            "started_at": None, "completed_at": None, "current_epoch": 3,
            "total_epochs": 3, "checkpoint_path": "/outputs/bi-mat-cua-A.pt",
            "test_acc": 0.9, "test_f1": 0.9, "error_message": None,
            "promoted_at": None, "tenant_id": A,
        })
    with _migration_cursor() as cur:
        cur.execute("SELECT set_config('app.system_scope','on',false)")
        # `tenant_id` suy ra từ hàng job cha, y như `insert_training_metric`.
        # Fixture tự khai một tenant sẽ dựng được trạng thái mà hợp đồng cấm —
        # và ở đây ta muốn dữ liệu HỢP LỆ để đo đường đọc, không phải dữ liệu
        # lệch để đo ràng buộc (ca đó nằm ở `test_c3_metric_ownership.py`).
        cur.execute(
            "INSERT INTO training_metrics(job_id, epoch, train_loss, train_acc,"
            " val_loss, val_acc, val_f1, tenant_id) "
            "SELECT %s,1,0.1,0.9,0.2,0.88,0.87, j.tenant_id "
            "FROM training_jobs j WHERE j.job_id = %s",
            (jid, jid))
    yield jid
    with _migration_cursor() as cur:
        cur.execute("SELECT set_config('app.system_scope','on',false)")
        cur.execute("DELETE FROM training_metrics WHERE job_id = %s", (jid,))
        cur.execute("DELETE FROM training_jobs WHERE job_id = %s", (jid,))


def test_pham_vi_dung_thi_doc_duoc(job_cua_A):
    """Chốt hiệu lực: hàng có thật và đọc được khi đúng phạm vi."""
    with tenant_scope(A):
        assert get_training_job(job_cua_A)


def test_pham_vi_khac_thi_KHONG_doc_duoc(job_cua_A):
    with tenant_scope(B):
        assert get_training_job(job_cua_A) is None


def test_KHONG_pham_vi_thi_cung_KHONG_doc_duoc(job_cua_A):
    """★ Câu hỏi trung tâm của tệp này.

    Đỏ ở đây nghĩa là RLS fail-OPEN khi không có phạm vi, và khi đó endpoint
    WebSocket — vốn chạy ngoài mọi phạm vi — đọc được job của mọi tổ chức.
    """
    with no_scope():
        r = get_training_job(job_cua_A)
    print(f"\n[evidence] doc khong pham vi -> {bool(r)}")
    assert r is None, (
        "RLS fail-OPEN: truy vấn không có phạm vi vẫn trả về hàng. Endpoint "
        "WebSocket chạy ngoài phạm vi nên đây là kênh đọc chéo tổ chức.")


def test_chi_so_KHONG_pham_vi(job_cua_A):
    """`training_metrics` giờ có `tenant_id` + RLS + FORCE — VÁ NGÀY 16/08/2026.

    Lịch sử của ca này đáng giữ lại, vì nó là một vòng đời hoàn chỉnh của một
    món nợ:

    ```
    đo được, chưa vá  ->  xfail(strict=True)   -> dấu nợ, không mất phép đo
    vá xong           ->  XPASS => suite ĐỎ    -> buộc quay lại gỡ dấu
    gỡ dấu            ->  khẳng định THẬT       -> nợ đóng, phép đo còn nguyên
    ```

    `strict=True` chính là thứ làm bước hai xảy ra. Một `xfail` không strict sẽ
    lặng lẽ xanh sau khi vá, và dấu nợ nằm lại vĩnh viễn trên một ca không còn
    đo gì.

    Ca này giữ nguyên chỗ đứng của nó: đo hành vi khi KHÔNG có phạm vi — đúng
    trạng thái mà endpoint WebSocket từng chạy. Hợp đồng chi tiết của quyền sở
    hữu chỉ số nằm ở `test_c3_metric_ownership.py`.
    """
    with no_scope():
        rows = list_training_metrics(job_cua_A)
    print(f"\n[evidence] chi so doc khong pham vi -> {len(rows)} dong")
    assert rows == [], (
        f"đọc được {len(rows)} dòng chỉ số của A mà không cần phạm vi nào")


def test_chi_so_pham_vi_khac_thi_KHONG_doc_duoc(job_cua_A):
    """Bổ sung cùng lượt vá: cách ly giữa hai tổ chức, không chỉ 'không phạm vi'.

    "Không phạm vi thì rỗng" một mình chưa đủ — nó cũng đúng với một bảng chặn
    tất cả mọi người. Ca này chứng minh bảng vẫn phục vụ đúng chủ của nó.
    """
    with tenant_scope(B):
        rows = list_training_metrics(job_cua_A)
    with tenant_scope(A):
        cua_a = list_training_metrics(job_cua_A)
    print(f"\n[evidence] B={len(rows)} dong | A={len(cua_a)} dong")
    assert rows == []
    assert len(cua_a) == 1
