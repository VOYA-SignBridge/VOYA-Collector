"""C3 — đầu ra của một lượt huấn luyện có đọc được từ tổ chức khác không?

Chạy:
    bash scripts/run_tests.sh backend/tests/test_c3_job_read_confinement.py -q -s

Bất biến
========
```
Train(A)  ->  Outputs(A) chỉ A đọc được
          ->  và điều đó phải đúng ở CẢ tầng cache, không chỉ tầng CSDL
```

Vì sao tệp này tồn tại
======================
`routers/training.py:235` giữ một `dict` toàn tiến trình khoá theo `job_id`:

```python
training_jobs: Dict[str, Dict[str, Any]] = {}
```

và `_ensure_job_loaded` mở đầu bằng

```python
cached = training_jobs.get(job_id)
if cached and cached["job"].status in TERMINAL_STATUSES:
    return cached                    # ← không hỏi CSDL, nên không gặp RLS
```

RLS bảo vệ hàng trong Postgres. Một bản sao trong bộ nhớ tiến trình thì RLS
không biết gì cả — đúng lớp rò rỉ "cache/path" đã kiểm ở A2, lần này trên mặt
phẳng đầu ra huấn luyện. Và job ở trạng thái cuối là job có checkpoint, có chỉ
số, có ma trận nhầm lẫn: chính lúc nó đáng giá nhất thì nhánh cache lại là
nhánh được đi.

A2 không bắt được vì A2 soi `classes.py`, `dataset.py`, `tts.py` — không soi
đường huấn luyện. Đó là bài học về phạm vi của một lượt rà: nó chỉ chứng minh
được đúng những tệp nó mở ra.

Ghi chú về phép đo
==================
Hai tenant dùng CÙNG một tiến trình, cùng một `dict` — đúng như ngoài đời, nơi
một tiến trình backend phục vụ mọi tổ chức. Đo bằng hai tiến trình sẽ cho kết
quả đẹp và vô nghĩa.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.routers.training import router, training_jobs  # noqa: E402
from app.storage.metadata_db import (  # noqa: E402
    _migration_cursor,
    upsert_training_job,
)
from app.tenant_context import system_scope, tenant_scope  # noqa: E402

A = "iso_a"
B = "iso_b"
#: `users.id` là UUID trong lược đồ — không phải chuỗi tự do.
UID_A = "c3aaaaaa-0000-4000-8000-00000000000a"
UID_B = "c3bbbbbb-0000-4000-8000-00000000000b"


@pytest.fixture(scope="module")
def hai_nguoi_dung():
    """Hai tài khoản THẬT trong `users`, hai tenant khác nhau.

    Không dùng `dependency_overrides[get_current_user]` với một `dict` giả, và
    lý do là bài học đắt nhất của P0: bốn ca T từng cùng trả 403 và trông như
    ĐẠT, trong khi thật ra chúng chưa bao giờ đăng nhập được — đăng nhập sai
    trường, dùng cookie chứ không Bearer, thiếu CSRF. Một người dùng giả làm
    mọi tầng phía dưới nó ngừng được kiểm.

    Ở đây tầng phía dưới chính là thứ cần đo: `TenantScopeMiddleware` phân giải
    phạm vi bằng cách tra `users.tenant_id` từ token thật. Không có tài khoản
    thật thì không có phạm vi thật, và phép đo sẽ nói về một hệ thống khác.
    """
    from app.storage.metadata_db import insert_user

    for uid, tenant in ((UID_A, A), (UID_B, B)):
        with system_scope("test: tao tai khoan do luong"):
            insert_user({
                "id": uid, "username": f"c3-{tenant}",
                "email": f"{uid}@example.invalid",
                "password_hash": "x", "created_at": datetime.now(timezone.utc),
                "is_active": True, "is_admin": False,
                "tenant_id": tenant,
            })
    yield
    with _migration_cursor() as cur:
        cur.execute("SELECT set_config('app.system_scope','on',false)")
        # `users.id` là uuid; thiếu ép kiểu thì Postgres báo `uuid = text`
        # và lượt dọn im lặng hỏng — đúng cái bẫy đã làm thư hỗ trợ không bao
        # giờ gửi được.
        cur.execute("DELETE FROM users WHERE id = ANY(%s::uuid[])",
                    ([UID_A, UID_B],))


@pytest.fixture
def app_client(hai_nguoi_dung):
    """★ `TenantScopeMiddleware` phải có mặt, và điều này KHÔNG phải chi tiết.

    Bản đầu của tệp này dựng app chỉ với router. Nó báo rò rỉ cả ở nhánh CSDL —
    một kết quả SAI, do chính dụng cụ đo: không có middleware thì không lượt gọi
    nào đặt phạm vi tenant, nên truy vấn chạy ngoài phạm vi và RLS không có gì
    để so. Ứng dụng thật luôn có middleware này (`main.py:117`).

    Đây đúng loại lỗi mà nhóm "bẫy của bộ đo" ghi lại: dụng cụ tự sinh ra hiện
    tượng nó đang đo. Báo một lỗ hổng sản xuất dựa trên một app thiếu tầng bảo
    vệ của sản xuất là báo sai — và báo sai về bảo mật thì đắt cả hai chiều.
    """
    from app.tenant_middleware import TenantScopeMiddleware

    app = FastAPI()
    app.include_router(router)
    app.add_middleware(TenantScopeMiddleware)
    training_jobs.clear()
    with TestClient(app) as c:
        yield c
    training_jobs.clear()


def _nhu(uid: str) -> Dict[str, str]:
    """Header của một phiên THẬT. Middleware và `get_current_user` cùng đọc nó."""
    from app import auth

    return {"Authorization": f"Bearer {auth.create_access_token({'sub': uid})}"}


@pytest.fixture
def job_cua_A():
    """Một job ĐÃ HOÀN THÀNH thuộc `iso_a`, ghi thật vào Postgres."""
    jid = str(uuid.uuid4())
    row = {
        "job_id": jid, "status": "completed", "model_type": "tcn",
        "config": {"model_type": "tcn"}, "auth_user_id": None,
        "created_at": None, "started_at": None, "completed_at": None,
        "current_epoch": 5, "total_epochs": 5,
        "checkpoint_path": "/outputs/bi-mat-cua-A.pt",
        "test_acc": 0.97, "test_f1": 0.96, "error_message": None,
        "promoted_at": None, "tenant_id": A,
    }
    with tenant_scope(A):
        upsert_training_job(row)
    yield jid
    with _migration_cursor() as cur:
        cur.execute("SELECT set_config('app.system_scope','on',false)")
        cur.execute("DELETE FROM training_metrics WHERE job_id = %s", (jid,))
        cur.execute("DELETE FROM training_jobs WHERE job_id = %s", (jid,))


# =========================================================================
# Tầng CSDL — RLS có làm việc của nó không
# =========================================================================

def test_tang_CSDL_khong_cho_B_doc_job_cua_A(job_cua_A):
    """Nền móng. Nếu ca này đỏ thì mọi ca sau vô nghĩa."""
    from app.storage.metadata_db import get_training_job

    with tenant_scope(A):
        cua_a = get_training_job(job_cua_A)
    with tenant_scope(B):
        cua_b = get_training_job(job_cua_A)

    print(f"\n[evidence] A doc duoc: {bool(cua_a)} | B doc duoc: {bool(cua_b)}")
    assert cua_a and cua_a["tenant_id"] == A
    assert cua_b is None, "RLS không chặn được B ở tầng CSDL"


def test_hang_that_su_ton_tai_khong_phai_RLS_giau_ca_khoi_A(job_cua_A):
    """Chốt hiệu lực cho ca trên.

    `B đọc ra None` cũng là kết quả khi hàng KHÔNG tồn tại — và khi đó ca trên
    xanh mà không chứng minh gì. Ca này khẳng định hàng có thật.
    """
    with system_scope("test: doc duoi sentinel he thong"):
        with _migration_cursor() as cur:
            cur.execute("SELECT set_config('app.system_scope','on',false)")
            cur.execute("SELECT tenant_id FROM training_jobs WHERE job_id = %s",
                        (job_cua_A,))
            r = cur.fetchone()
    print(f"\n[evidence] hang that mang tenant {r and r[0]!r}")
    assert r and r[0] == A


# =========================================================================
# Tầng CACHE — nơi RLS không với tới
# =========================================================================

class TestCacheToanTienTrinh:

    def test_B_khong_doc_duoc_job_cua_A_qua_API(self, app_client, job_cua_A):
        """★ Ca trung tâm: A xem job của mình, rồi B hỏi đúng `job_id` đó.

        Lượt gọi thứ nhất nạp job vào `training_jobs` — bộ nhớ dùng chung của
        tiến trình. Lượt thứ hai đến từ một tổ chức khác nhưng cùng tiến trình.
        """
        r_a = app_client.get(f"/training/jobs/{job_cua_A}", headers=_nhu(UID_A))
        print(f"\n[evidence] A: {r_a.status_code}")
        assert r_a.status_code == 200, r_a.text
        assert job_cua_A in training_jobs, (
            "lượt gọi của A phải nạp job vào cache — nếu không, ca này không "
            "đo được nhánh cache")

        r_b = app_client.get(f"/training/jobs/{job_cua_A}", headers=_nhu(UID_B))
        print(f"[evidence] B: {r_b.status_code} {r_b.text[:200]}")

        assert r_b.status_code == 404, (
            f"B đọc được job của A qua cache toàn tiến trình. "
            f"Thân: {r_b.text[:400]}")

    def test_B_khong_thay_duong_dan_checkpoint_cua_A(self, app_client, job_cua_A):
        """Rò rỉ ở đây không dừng ở siêu dữ liệu.

        `checkpoint_path` là đường dẫn tới hiện vật mô hình đã huấn luyện. Lộ nó
        là lộ vị trí sản phẩm cuối của một tổ chức khác.
        """
        app_client.get(f"/training/jobs/{job_cua_A}", headers=_nhu(UID_A))

        r = app_client.get(f"/training/jobs/{job_cua_A}", headers=_nhu(UID_B))
        assert "bi-mat-cua-A" not in r.text, "lộ đường dẫn checkpoint của A"

    def test_B_khong_doc_duoc_chi_so_cua_A(self, app_client, job_cua_A):
        """`training_metrics` KHÔNG có `tenant_id` và KHÔNG có RLS.

        Đo được ở sổ kiểm kê C3. Nó dựa hoàn toàn vào việc cổng ở hàng job cha
        chặn trước — nên nếu cổng đó thủng thì chỉ số đi theo.
        """
        app_client.get(f"/training/jobs/{job_cua_A}", headers=_nhu(UID_A))

        r = app_client.get(f"/training/jobs/{job_cua_A}/metrics", headers=_nhu(UID_B))
        print(f"\n[evidence] progress cho B: {r.status_code} {r.text[:160]}")
        assert r.status_code == 404

    def test_B_khong_doc_duoc_danh_gia_cua_A(self, app_client, job_cua_A):
        app_client.get(f"/training/jobs/{job_cua_A}", headers=_nhu(UID_A))

        r = app_client.get(f"/training/jobs/{job_cua_A}/evaluation", headers=_nhu(UID_B))
        print(f"\n[evidence] evaluation cho B: {r.status_code} {r.text[:160]}")
        assert r.status_code == 404

    def test_khong_co_cache_thi_B_van_khong_doc_duoc(self, app_client, job_cua_A):
        """Tách hai nguyên nhân.

        Nếu ca này ĐỎ thì lỗ nằm ở đường CSDL, không phải ở cache; nếu nó XANH
        còn ca trung tâm ĐỎ thì lỗ đúng là ở cache. Không có ca này thì một bản
        vá sai chỗ vẫn làm mọi thứ xanh.
        """
        training_jobs.clear()
        r = app_client.get(f"/training/jobs/{job_cua_A}", headers=_nhu(UID_B))
        print(f"\n[evidence] cache rong, B hoi: {r.status_code}")
        assert r.status_code == 404
