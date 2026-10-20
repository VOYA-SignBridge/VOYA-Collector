"""C3-M — chỉ số huấn luyện thuộc về tổ chức sở hữu JOB, và CSDL tự giữ điều đó.

Chạy:
    bash scripts/run_tests.sh backend/tests/test_c3_metric_ownership.py -v -s

Bất biến
========
```
metric.tenant_id  ==  parent_job.tenant_id      (CSDL cưỡng chế, không phải mã)
metric của A      ->  chỉ A đọc được
metric mồ côi     ->  KHÔNG tạo được
```

Vì sao bảng con cũng cần quyền sở hữu
=====================================
Trước 16/08/2026:

```
training_jobs      tenant_id + RLS + FORCE + policy
training_metrics   không tenant_id, không RLS, không policy
```

Quyền sở hữu của đầu ra đứt đúng ở bảng con. Cổng duy nhất bảo vệ chỉ số là
hàng job cha, nên bất kỳ đường đọc nào không đi qua hàng cha đều đọc được chỉ
số của mọi tổ chức — và đã có một đường như vậy: endpoint WebSocket, chạy ngoài
mọi phạm vi vì `TenantScopeMiddleware` bỏ qua `scope["type"] != "http"`.

Backfill ở đây HỢP LỆ
=====================
Khác hẳn hai hiện vật vận hành mất chủ ở C2b. Ở đó không có nguồn nào nói hiện
vật thuộc về ai, nên gán chủ là phỏng đoán. Ở đây có một quan hệ cha đã lưu:

```
training_metrics.job_id  ->  training_jobs.job_id  ->  training_jobs.tenant_id
```

Chủ sở hữu được TRA RA. Có provenance thì có quyền backfill — và chỉ số nào
không tra được job cha thì migration DỪNG, không suy về `default`.

Hai lưới, không phải một
========================
```
lưới 1  `insert_training_metric` suy tenant từ job cha NGAY trong câu INSERT
lưới 2  khoá ngoại GHÉP (tenant_id, job_id) -> training_jobs(tenant_id, job_id)
```

Lưới 2 không phụ thuộc mã ứng dụng. Chỉ có lưới 1 thì một lượt gọi sai sinh ra
một hàng trông hợp lệ với mọi phép kiểm phía trên nó.
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
    insert_training_metric,
    list_training_metrics,
    upsert_training_job,
)
from app.tenancy import DEFAULT_TENANT_ID  # noqa: E402
from app.tenant_context import no_scope, tenant_scope  # noqa: E402

A = "iso_a"
B = "iso_b"


def _job(tenant: str) -> str:
    jid = str(uuid.uuid4())
    with tenant_scope(tenant):
        upsert_training_job({
            "job_id": jid, "status": "completed", "model_type": "tcn",
            "config": {}, "auth_user_id": None, "created_at": None,
            "started_at": None, "completed_at": None, "current_epoch": 1,
            "total_epochs": 1, "checkpoint_path": None, "test_acc": None,
            "test_f1": None, "error_message": None, "promoted_at": None,
            "tenant_id": tenant,
        })
    return jid


def _metric(job_id: str, epoch: int = 1) -> dict:
    return {"job_id": job_id, "epoch": epoch, "train_loss": 0.1,
            "train_acc": 0.9, "val_loss": 0.2, "val_acc": 0.88, "val_f1": 0.87}


def _doc_he_thong(sql: str, params=()):
    with _migration_cursor() as cur:
        cur.execute("SELECT set_config('app.system_scope','on',false)")
        cur.execute(sql, params)
        return cur.fetchall()


@pytest.fixture
def job_A():
    jid = _job(A)
    yield jid
    _doc_he_thong("DELETE FROM training_jobs WHERE job_id = %s RETURNING job_id",
                  (jid,))


@pytest.fixture
def job_B():
    jid = _job(B)
    yield jid
    _doc_he_thong("DELETE FROM training_jobs WHERE job_id = %s RETURNING job_id",
                  (jid,))


# =========================================================================
# C3-M1 / C3-M2 — đọc
# =========================================================================

def test_C3_M1_chi_so_cua_A_thi_A_doc_duoc(job_A):
    with tenant_scope(A):
        insert_training_metric(_metric(job_A))
        rows = list_training_metrics(job_A)
    print(f"\n[evidence] A doc duoc {len(rows)} dong")
    assert len(rows) == 1
    assert rows[0]["tenant_id"] == A


def test_C3_M2_chi_so_cua_A_thi_B_KHONG_doc_duoc(job_A):
    """★ Bất biến trung tâm. Trước lượt này bảng không có RLS nào cả."""
    with tenant_scope(A):
        insert_training_metric(_metric(job_A))
    with tenant_scope(B):
        rows = list_training_metrics(job_A)
    print(f"\n[evidence] B doc duoc {len(rows)} dong")
    assert rows == []


def test_hang_that_su_ton_tai_khong_phai_khong_ai_ghi(job_A):
    """Chốt hiệu lực cho ca trên.

    "B đọc ra rỗng" cũng là kết quả khi KHÔNG có hàng nào — và khi đó ca trên
    xanh mà chưa chứng minh gì. Đọc dưới sentinel hệ thống để thấy hàng thật.
    """
    with tenant_scope(A):
        insert_training_metric(_metric(job_A))
    r = _doc_he_thong(
        "SELECT tenant_id FROM training_metrics WHERE job_id = %s", (job_A,))
    print(f"\n[evidence] hang that: {r}")
    assert len(r) == 1 and r[0][0] == A


# =========================================================================
# C3-M3 — không phạm vi
# =========================================================================

def test_C3_M3_doc_KHONG_pham_vi_thi_ra_rong(job_A):
    """Đây là ca đã ĐỎ trước bản vá, giữ bằng `xfail(strict=True)`.

    Endpoint WebSocket từng chạy đúng trong trạng thái này: không phạm vi nào
    cả. Nay bảng có RLS nên câu hỏi "không phạm vi thì thấy gì" có một câu trả
    lời, và câu trả lời là: không thấy gì.
    """
    with tenant_scope(A):
        insert_training_metric(_metric(job_A))
    with no_scope():
        rows = list_training_metrics(job_A)
    print(f"\n[evidence] khong pham vi doc duoc {len(rows)} dong")
    assert rows == []


# =========================================================================
# C3-M4 — CSDL tự chặn, không nhờ mã ứng dụng
# =========================================================================

def test_C3_M4_metric_tenant_A_gan_vao_job_cua_B_bi_CSDL_TU_CHOI(job_B):
    """★ Lưới thứ hai: khoá ngoại GHÉP.

    Ca này đi VÒNG QUA `insert_training_metric` — cố ý. Hàm ấy suy tenant từ
    job cha nên tự nó không sinh ra được trạng thái lệch; nếu chỉ kiểm qua nó
    thì ta đang kiểm hàm, không kiểm ràng buộc. Câu INSERT thô dưới đây dựng
    đúng trạng thái mà hợp đồng cấm, và CSDL phải là thứ nói không.
    """
    with pytest.raises(Exception) as loi:
        _doc_he_thong(
            "INSERT INTO training_metrics(job_id, epoch, tenant_id) "
            "VALUES (%s, 1, %s) RETURNING job_id", (job_B, A))
    print(f"\n[evidence] {type(loi.value).__name__}: {str(loi.value)[:120]}")
    assert "fk_training_metrics_job_tenant" in str(loi.value).lower() \
        or "foreign key" in str(loi.value).lower()


def test_khoa_ngoai_ghep_va_UNIQUE_cha_deu_ton_tai():
    """Ràng buộc phải CÓ THẬT, không chỉ có trong danh sách migration.

    "Câu lệnh đã đăng ký" và "ràng buộc đang có hiệu lực" là hai sự thật khác
    nhau: `_run_ddl` nuốt lỗi rồi đi tiếp, nên một câu hỏng chỉ để lại một dòng
    cảnh báo. Bài học từ `_DROP_USERS_TENANT_DEFAULT` — đăng ký nhưng chết.
    """
    r = _doc_he_thong(
        "SELECT conname FROM pg_constraint WHERE conname IN "
        "('fk_training_metrics_job_tenant','uq_training_jobs_tenant_job')")
    ten = sorted(x[0] for x in r)
    print(f"\n[evidence] {ten}")
    assert ten == ["fk_training_metrics_job_tenant", "uq_training_jobs_tenant_job"]


def test_luoc_do_giu_NOT_NULL_va_khong_co_DEFAULT():
    r = _doc_he_thong(
        "SELECT is_nullable, column_default FROM information_schema.columns "
        "WHERE table_name='training_metrics' AND column_name='tenant_id'")
    print(f"\n[evidence] is_nullable={r[0][0]} default={r[0][1]!r}")
    assert r[0][0] == "NO"
    assert r[0][1] is None


def test_RLS_va_FORCE_deu_bat():
    r = _doc_he_thong(
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE oid = 'public.training_metrics'::regclass")
    p = _doc_he_thong(
        "SELECT count(*) FROM pg_policies WHERE tablename='training_metrics'")
    print(f"\n[evidence] rls={r[0][0]} force={r[0][1]} policy={p[0][0]}")
    assert r[0][0] and r[0][1] and p[0][0] == 1


# =========================================================================
# C3-M5 — tenant được SUY RA từ cha, không do người gọi khai
# =========================================================================

def test_C3_M5_tenant_lay_tu_job_cha_chu_khong_tu_nguoi_goi(job_A):
    """Người gọi cố khai `tenant_id` — giá trị ấy phải bị BỎ QUA.

    Chữ ký của `insert_training_metric` không nhận `tenant_id`, nhưng người gọi
    truyền thêm khoá vào `dict` thì psycopg2 chỉ đơn giản không dùng tới. Ca này
    khẳng định điều đó đúng, thay vì giả định.
    """
    hang = _metric(job_A)
    hang["tenant_id"] = B                      # người gọi cố khai iso_b
    with tenant_scope(A):
        insert_training_metric(hang)
    r = _doc_he_thong(
        "SELECT tenant_id FROM training_metrics WHERE job_id = %s", (job_A,))
    print(f"\n[evidence] nguoi goi khai {B!r} -> luu {r[0][0]!r}")
    assert r[0][0] == A


def test_job_khong_ton_tai_thi_KHONG_tao_chi_so_mo_coi():
    """Không có job cha thì `SELECT` không ra dòng nào, nên không ghi gì.

    Đây là hệ quả ta MUỐN của việc suy tenant trong chính câu INSERT: thay vì
    tạo một chỉ số không tra được chủ, lượt ghi lặng lẽ không làm gì.
    """
    ma = str(uuid.uuid4())
    with tenant_scope(A):
        insert_training_metric(_metric(ma))
    r = _doc_he_thong(
        "SELECT count(*) FROM training_metrics WHERE job_id = %s", (ma,))
    print(f"\n[evidence] chi so mo coi tao ra: {r[0][0]}")
    assert r[0][0] == 0


def test_tien_trinh_thuoc_to_chuc_khac_KHONG_ghi_duoc_vao_job_cua_A(job_A):
    """`training_jobs` nằm dưới RLS, nên câu `SELECT` trong INSERT cũng bị lọc.

    Hệ quả: một lượt ghi chạy dưới phạm vi B không tìm thấy job của A, nên
    không ghi được chỉ số vào job đó — cách ly cả chiều GHI, không chỉ chiều
    đọc.
    """
    with tenant_scope(B):
        insert_training_metric(_metric(job_A, epoch=7))
    r = _doc_he_thong(
        "SELECT count(*) FROM training_metrics WHERE job_id = %s AND epoch = 7",
        (job_A,))
    print(f"\n[evidence] B ghi duoc vao job cua A: {r[0][0]} dong")
    assert r[0][0] == 0


# =========================================================================
# C3-M6 — không chỉ số nào rơi về tenant khởi tạo
# =========================================================================

def test_C3_M6_khong_chi_so_nao_lech_tenant_cua_job_cha():
    """Hậu điều kiện của migration, kiểm lại như một BẤT BIẾN sống.

    Hai vế, và vế thứ hai mới là vế bảo mật: "đã điền" khác "điền ĐÚNG". Một
    bản vá gán tất cả về `default` vẫn đạt vế một.
    """
    r = _doc_he_thong(
        "SELECT count(*) FROM training_metrics m "
        "LEFT JOIN training_jobs j ON j.job_id = m.job_id "
        "WHERE m.tenant_id IS NULL OR j.job_id IS NULL "
        "   OR m.tenant_id IS DISTINCT FROM j.tenant_id")
    print(f"\n[evidence] chi so lech/mo coi/thieu tenant: {r[0][0]}")
    assert r[0][0] == 0


def test_C3_M6_chi_so_cua_job_khong_thuoc_default_thi_khong_mang_default(job_A):
    """`default` chỉ đúng khi job cha THẬT SỰ thuộc `default`."""
    with tenant_scope(A):
        insert_training_metric(_metric(job_A))
    r = _doc_he_thong(
        "SELECT count(*) FROM training_metrics WHERE job_id = %s AND tenant_id = %s",
        (job_A, DEFAULT_TENANT_ID))
    print(f"\n[evidence] roi ve {DEFAULT_TENANT_ID!r}: {r[0][0]} dong")
    assert r[0][0] == 0
