"""Hợp đồng đầu ra của model: ánh xạ chỉ số → nhãn, đóng băng lúc train xong.

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

# ------------------------------------------- hợp đồng đầu ra của model

@pytest.fixture
def a_job():
    """Một job thật, dọn sạch sau khi xong."""
    from app.tenant_context import system_scope

    job_id = f"testjob{uuid.uuid4().hex[:8]}"
    with system_scope("test: hop dong dau ra"):
        db._execute(
            "INSERT INTO training_jobs(job_id, status, tenant_id) VALUES(%s, 'completed', 'default')",
            (job_id,))
        try:
            yield job_id
        finally:
            # `training_job_classes` là ON DELETE CASCADE nên xoá job là đủ.
            db._execute("DELETE FROM training_jobs WHERE job_id = %s", (job_id,))


def test_the_output_contract_is_written_in_index_order(a_job):
    from app.tenant_context import system_scope

    with system_scope("test: hop dong dau ra"):
        db.replace_training_job_classes(
            job_id=a_job, tenant_id="default",
            pairs=[(0, "mot"), (1, "hai"), (2, "ba")])
        rows = db.list_training_job_classes(a_job)

    assert [r["class_idx"] for r in rows] == [0, 1, 2]
    assert [r["label"] for r in rows] == ["mot", "hai", "ba"]


def test_retraining_replaces_the_contract_instead_of_stacking(a_job):
    """Celery giao trùng hoặc người dùng chạy lại phải cho ra ĐÚNG một tập lớp.
    Hai tập chồng lên nhau nghĩa là chỉ số đầu ra không còn xác định."""
    from app.tenant_context import system_scope

    with system_scope("test: hop dong dau ra"):
        db.replace_training_job_classes(
            job_id=a_job, tenant_id="default", pairs=[(0, "cu"), (1, "cu2")])
        db.replace_training_job_classes(
            job_id=a_job, tenant_id="default", pairs=[(0, "moi")])
        rows = db.list_training_job_classes(a_job)

    assert len(rows) == 1 and rows[0]["label"] == "moi"


def test_an_unmatched_label_is_still_recorded(a_job):
    """`label` là hợp đồng; `class_uid` chỉ là đường dẫn tiện lợi và được phép
    NULL. Một nhãn không tra được vào danh mục vẫn PHẢI được lưu — bỏ nó đi là
    làm hụt không gian đầu ra của model."""
    from app.tenant_context import system_scope

    with system_scope("test: hop dong dau ra"):
        db.replace_training_job_classes(
            job_id=a_job, tenant_id="default",
            pairs=[(0, f"nhan-khong-ton-tai-{uuid.uuid4().hex[:6]}")])
        rows = db.list_training_job_classes(a_job)

    assert len(rows) == 1
    assert rows[0]["class_uid"] is None


def test_deleting_a_job_takes_its_contract_with_it():
    """ON DELETE CASCADE ở đây là đúng, ngược với `tenants`: hợp đồng đầu ra
    không có nghĩa gì nếu job không còn."""
    from app.tenant_context import system_scope

    job_id = f"testjob{uuid.uuid4().hex[:8]}"
    with system_scope("test: cascade hop dong"):
        db._execute(
            "INSERT INTO training_jobs(job_id, status, tenant_id) VALUES(%s, 'completed', 'default')",
            (job_id,))
        db.replace_training_job_classes(
            job_id=job_id, tenant_id="default", pairs=[(0, "x")])
        db._execute("DELETE FROM training_jobs WHERE job_id = %s", (job_id,))
        left = db._fetch_all(
            "SELECT count(*) AS n FROM training_job_classes WHERE job_id = %s", (job_id,))
    assert left[0]["n"] == 0

