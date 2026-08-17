"""Ràng buộc có CHẶN THẬT không — khoá ngoại và đồng ý của người ký.

Tách từ `test_schema_v3.py` (593 dòng, bốn mối quan tâm không liên quan gộp
chung). Bối cảnh đầy đủ của đợt vá lược đồ: `docs/02-data/SAAS_SCHEMA_DESIGN.md`
§9sexies.
"""

from __future__ import annotations

import uuid

import psycopg2
import pytest

from app.storage import metadata_db as db


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture(scope="module", autouse=True)
def _corpus(_ensure_schema, corpus_row_to_poke):
    """Mọi test dưới đây sửa một dòng CÓ SẴN để chứng minh ràng buộc chặn.

    Trên CSDL rỗng thì không có dòng nào để sửa, `UPDATE` chạm 0 hàng, và
    `pytest.raises` đỏ với thông báo "DID NOT RAISE" — nghe như ràng buộc biến
    mất. Xem `conftest.corpus_row_to_poke`.
    """
    return corpus_row_to_poke

# --------------------------------------------------------- khoá ngoại chặn thật

# `rollback_cursor` nay o conftest.py: ba file tung chep ba ban gan giong
# nhau cua no, va mot ban da suyt thieu `apply_scope` — thieu no thi ket qua
# doi nghia hoan toan.

def test_a_sample_cannot_point_at_a_session_that_does_not_exist(rollback_cursor):
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        rollback_cursor.execute(
            "UPDATE samples SET capture_session_id = %s "
            "WHERE sample_uid = (SELECT sample_uid FROM samples LIMIT 1)",
            (str(uuid.uuid4()),))


def test_a_sample_cannot_point_at_a_signer_that_does_not_exist(rollback_cursor):
    """899 mẫu từng ở đúng trạng thái này và không gì phản đối."""
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        rollback_cursor.execute(
            "UPDATE samples SET signer_id = 'KHONG_TON_TAI' "
            "WHERE sample_uid = (SELECT sample_uid FROM samples LIMIT 1)")


def test_a_class_cannot_name_a_vocabulary_group_that_does_not_exist(rollback_cursor):
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        rollback_cursor.execute(
            "UPDATE classes SET vocabulary_group = 'nhom_bia_dat' "
            "WHERE class_uid = (SELECT class_uid FROM classes LIMIT 1)")


def test_training_metrics_cannot_orphan_itself(rollback_cursor):
    """Phải truyền `tenant_id`, nếu không khoá ngoại KHÔNG hề được hỏi tới.

    Đợt C3 gắn `tenant_id NOT NULL` cho bảng này. Bản cũ chèn thiếu cột đó, nên
    câu lệnh ngã ở `NotNullViolation` — trước khi khoá ngoại kịp chạy. Test đỏ,
    nhưng đỏ vì một ràng buộc KHÁC với ràng buộc đang thử nghiệm, và thông báo
    lỗi không hề nói ra điều đó. Đây là mặt còn lại của cái bẫy mà docstring của
    `rollback_cursor` cảnh báo: ở đó một test xanh vì sai lý do, ở đây một test
    đỏ vì sai lý do — cùng một hậu quả là ràng buộc dưới thử nghiệm không chạy.
    """
    from app.tenancy import DEFAULT_TENANT_ID

    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        rollback_cursor.execute(
            "INSERT INTO training_metrics(tenant_id, job_id, epoch) "
            "VALUES(%s, 'khong_co_job', 1)",
            (DEFAULT_TENANT_ID,))


def test_a_signer_cannot_point_at_a_deleted_account(rollback_cursor):
    """Cái lỗ đã để 20 dòng rác sống sót: `external_user_id` từng là TEXT."""
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        rollback_cursor.execute(
            "UPDATE signers SET external_user_id = %s "
            "WHERE signer_id = (SELECT signer_id FROM signers LIMIT 1)",
            (str(uuid.uuid4()),))


def test_a_sample_cannot_reach_across_tenants_for_its_class(rollback_cursor):
    """Khoá ngoại một cột cũ CHO PHÉP điều này; khoá ghép thì không.

    Dựng một tenant thứ hai với lớp riêng, rồi thử trỏ một mẫu của tenant
    `default` sang lớp đó. Trước v3 câu này chạy thành công.
    """
    tid = f"t{uuid.uuid4().hex[:8]}"
    cuid = uuid.uuid4().hex[:12]
    rollback_cursor.execute(
        "INSERT INTO tenants(tenant_id, display_name, slug) VALUES(%s, %s, %s)",
        (tid, "Tenant thử", tid))
    rollback_cursor.execute(
        "INSERT INTO classes(class_uid, tenant_id, slug) VALUES(%s, %s, %s)",
        (cuid, tid, "lop-cua-tenant-khac"))
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        rollback_cursor.execute(
            "UPDATE samples SET class_uid = %s "
            "WHERE sample_uid = (SELECT sample_uid FROM samples "
            "                    WHERE tenant_id = 'default' LIMIT 1)",
            (cuid,))


def test_two_sessions_cannot_share_the_same_natural_key(rollback_cursor):
    """(tenant, class, session_id) là danh tính mà `label_sessions.py` dùng."""
    rollback_cursor.execute(
        "SELECT tenant_id, class_uid, session_id FROM capture_sessions LIMIT 1")
    row = rollback_cursor.fetchone()
    if row is None:
        pytest.skip("chưa có phiên thu nào để đối chiếu")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        rollback_cursor.execute(
            "INSERT INTO capture_sessions(capture_session_id, tenant_id, class_uid, session_id) "
            "VALUES(%s, %s, %s, %s)", (str(uuid.uuid4()), *row))


def test_a_session_id_cannot_be_blank(rollback_cursor):
    """997 mẫu mang `session_id = ''`. Chúng cố ý KHÔNG được gom thành phiên —
    gom lại sẽ đẻ ra hàng trăm phiên chưa từng diễn ra."""
    rollback_cursor.execute("SELECT tenant_id, class_uid FROM classes LIMIT 1")
    tenant_id, class_uid = rollback_cursor.fetchone()
    with pytest.raises(psycopg2.errors.CheckViolation):
        rollback_cursor.execute(
            "INSERT INTO capture_sessions(capture_session_id, tenant_id, class_uid, session_id) "
            "VALUES(%s, %s, %s, '')", (str(uuid.uuid4()), tenant_id, class_uid))


# ------------------------------------------------------- đồng ý của người ký

def test_signer_consent_requires_a_published_document(rollback_cursor):
    """Không thể ghi nhận đồng ý với một văn bản không tồn tại. Bằng chứng
    đồng ý mà không chỉ được vào bản điều khoản nào thì không phải bằng chứng."""
    rollback_cursor.execute("SELECT tenant_id, signer_id FROM signers LIMIT 1")
    tenant_id, signer_id = rollback_cursor.fetchone()
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        rollback_cursor.execute(
            "INSERT INTO signer_consents"
            "(consent_id, tenant_id, signer_id, scope, kind, version) "
            "VALUES(%s, %s, %s, 'public_library', 'guardian', 'khong-co-ban-nay')",
            (str(uuid.uuid4()), tenant_id, signer_id))


def test_signer_consent_scope_is_constrained(rollback_cursor):
    """Ba mức tăng dần. Đồng ý cho huấn luyện nội bộ KHÔNG kéo theo đồng ý cho
    công bố công khai, nên `scope` không được là chuỗi tự do."""
    rollback_cursor.execute("SELECT tenant_id, signer_id FROM signers LIMIT 1")
    tenant_id, signer_id = rollback_cursor.fetchone()
    with pytest.raises(psycopg2.errors.CheckViolation):
        rollback_cursor.execute(
            "INSERT INTO signer_consents"
            "(consent_id, tenant_id, signer_id, scope, kind, version) "
            "VALUES(%s, %s, %s, 'tuy_tien', 'guardian', 'v1')",
            (str(uuid.uuid4()), tenant_id, signer_id))


def test_only_one_live_consent_per_signer_and_scope(rollback_cursor):
    """Rút rồi cấp lại là hai dòng; hai dòng CÙNG còn hiệu lực thì không."""
    rollback_cursor.execute("SELECT tenant_id, signer_id FROM signers LIMIT 1")
    tenant_id, signer_id = rollback_cursor.fetchone()
    rollback_cursor.execute(
        "INSERT INTO legal_documents(doc_id, kind, version, effective_from, "
        "content_hash, url, title, requires_reconsent) "
        "VALUES(%s, 'guardian', 'test-v1', NOW(), 'hash', '/x', 'Thử', FALSE)",
        (str(uuid.uuid4()),))
    rollback_cursor.execute(
        "INSERT INTO signer_consents"
        "(consent_id, tenant_id, signer_id, scope, kind, version) "
        "VALUES(%s, %s, %s, 'public_library', 'guardian', 'test-v1')",
        (str(uuid.uuid4()), tenant_id, signer_id))
    with pytest.raises(psycopg2.errors.UniqueViolation):
        rollback_cursor.execute(
            "INSERT INTO signer_consents"
            "(consent_id, tenant_id, signer_id, scope, kind, version) "
            "VALUES(%s, %s, %s, 'public_library', 'guardian', 'test-v1')",
            (str(uuid.uuid4()), tenant_id, signer_id))


