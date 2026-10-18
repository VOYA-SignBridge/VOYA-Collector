"""Hợp đồng đầu ra của model: ánh xạ chỉ số → nhãn, đóng băng lúc train xong.

Tách từ `test_schema_v3.py` (593 dòng, bốn mối quan tâm không liên quan gộp
chung). Bối cảnh đầy đủ của đợt vá lược đồ: `docs/02-data/SAAS_SCHEMA_DESIGN.md`
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



# ------------------------------------------- checkpoint từ split vận hành

def test_checkpoint_label_pair_reads_the_original_label_from_a_dict_entry():
    """Checkpoint từ split vận hành lưu `idx_to_label[i]` là một dict. Ép nó qua
    `str()` ghi cả chuỗi `{'label_key': ...}` vào cột `label` (18/10/2026)."""
    from app.training_tasks import checkpoint_label_pair

    entry = {"label_key": "uid-1", "class_uid": "uid-1", "label_slug": "tom",
             "label_original": "tôm", "dialect": "hoa-de"}
    assert checkpoint_label_pair(entry) == ("tôm", "uid-1")
    # Thiếu nhãn gốc thì lùi về slug, rồi tới khoá.
    assert checkpoint_label_pair({"class_uid": "uid-2", "label_slug": "ca"}) == ("ca", "uid-2")
    assert checkpoint_label_pair({"label_key": "uid-3"}) == ("uid-3", "")


def test_checkpoint_label_pair_keeps_the_legacy_string_form():
    from app.training_tasks import checkpoint_label_pair

    assert checkpoint_label_pair("vn/alphabet/a") == ("vn/alphabet/a", "")


def test_a_class_uid_from_the_checkpoint_beats_a_lookup_by_name(a_job):
    """Hai phương ngữ có thể trùng `label_original`; `class_uid` có sẵn trong
    checkpoint phải được dùng, không đoán lại qua tên."""
    uid = f"testcls-{uuid.uuid4().hex[:10]}"
    with system_scope("test: hop dong dau ra"):
        db._execute("INSERT INTO classes(class_uid, tenant_id) VALUES(%s, 'default')", (uid,))
        try:
            db.replace_training_job_classes(
                job_id=a_job, tenant_id="default",
                pairs=[(0, "ten-khong-khop-voi-lop-nao", uid)])
            got = db.list_training_job_classes(a_job)
        finally:
            db._execute("DELETE FROM training_job_classes WHERE job_id = %s", (a_job,))
            db._execute("DELETE FROM classes WHERE class_uid = %s", (uid,))

    assert got[0]["class_uid"] == uid
    assert got[0]["label"] == "ten-khong-khop-voi-lop-nao"


def test_evaluation_labels_resolve_class_uids_to_the_original_label():
    """Ma trận nhầm lẫn của job từ split vận hành có khoá là UUID; người đọc cần
    thấy `label_original`. Khoá không tra được thì bị bỏ qua (giao diện lùi về cũ)."""
    from app.routers.training import _evaluation_label_names
    from app.tenant_context import tenant_scope

    uid = f"testcls-{uuid.uuid4().hex[:10]}"
    with system_scope("test: ten nhan evaluation"):
        db._execute(
            "INSERT INTO classes(class_uid, tenant_id, label_original, slug) "
            "VALUES(%s, 'default', 'lột da cá', 'lot-da-ca-test')", (uid,))
        try:
            with tenant_scope("default"):
                names = _evaluation_label_names([uid, "vn/alphabet/a", ""])
        finally:
            db._execute("DELETE FROM classes WHERE class_uid = %s", (uid,))

    assert names == {uid: "lột da cá"}
