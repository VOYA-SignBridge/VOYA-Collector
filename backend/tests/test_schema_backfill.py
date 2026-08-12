"""Backfill: chuyển đúng, và những chỗ CỐ Ý để trống thì phải còn trống.

Tách từ `test_schema_v3.py` (593 dòng, bốn mối quan tâm không liên quan gộp
chung). Bối cảnh đầy đủ của đợt vá lược đồ: `docs/needFix/SAAS_SCHEMA_DESIGN.md`
§9sexies.
"""

from __future__ import annotations


import pytest

from app.storage import metadata_db as db


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()

# --------------------------------------------------------------- backfill

def test_every_sample_with_a_real_session_id_got_linked():
    """2.863 mẫu có `session_id` thật, và không một mẫu nào trong số đó được
    phép còn treo sau backfill."""
    rows = db._fetch_all(
        "SELECT count(*) AS n FROM samples "
        "WHERE session_id IS NOT NULL AND session_id <> '' "
        "  AND capture_session_id IS NULL")
    assert rows[0]["n"] == 0


def test_blank_session_ids_were_left_unlinked_on_purpose():
    """Phía ngược lại: 997 mẫu `session_id = ''` PHẢI còn NULL. Gán cho chúng
    một phiên là bịa ra một sự kiện chưa từng xảy ra."""
    rows = db._fetch_all(
        "SELECT count(*) AS n FROM samples "
        "WHERE session_id = '' AND capture_session_id IS NOT NULL")
    assert rows[0]["n"] == 0


def test_a_session_never_claims_a_signer_it_cannot_prove():
    """15 nhóm (class, session_id) chứa nhiều người ký khác nhau.

    Backfill KHÔNG được chọn đại một người trong số đó: "phiên này do S010 thực
    hiện" khi thực tế có hai người là một khẳng định sai, và một khẳng định sai
    tệ hơn một ô trống vì không đọc ra được là nó sai. Chỉ điền khi cả nhóm
    đồng nhất.
    """
    rows = db._fetch_all(
        "SELECT count(*) AS n FROM capture_sessions cs WHERE cs.signer_id IS NOT NULL "
        "AND (SELECT count(DISTINCT s.signer_id) FROM samples s "
        "     WHERE s.tenant_id = cs.tenant_id AND s.class_uid = cs.class_uid "
        "       AND s.session_id = cs.session_id) <> 1")
    assert rows[0]["n"] == 0, (
        "một phiên thu đang khẳng định người ký mà các mẫu của nó không đồng ý"
    )


def test_a_session_never_claims_a_recorder_it_cannot_prove():
    rows = db._fetch_all(
        "SELECT count(*) AS n FROM capture_sessions cs WHERE cs.auth_user_id IS NOT NULL "
        "AND (SELECT count(DISTINCT s.auth_user_id) FROM samples s "
        "     WHERE s.tenant_id = cs.tenant_id AND s.class_uid = cs.class_uid "
        "       AND s.session_id = cs.session_id) <> 1")
    assert rows[0]["n"] == 0


def test_session_timestamps_bracket_their_samples():
    """Ngược lại với hai test trên: min/max `created_at` là phép ĐO trên chính
    nhóm đó, không phải một lựa chọn đại diện, nên luôn phải đúng."""
    rows = db._fetch_all(
        "SELECT count(*) AS n FROM capture_sessions cs JOIN samples s "
        "ON s.capture_session_id = cs.capture_session_id "
        "WHERE s.created_at < cs.started_at OR s.created_at > cs.ended_at")
    assert rows[0]["n"] == 0


def test_every_live_user_is_a_member_of_their_tenant():
    """`tenant_members` rỗng trong khi `users` có 10 dòng nghĩa là mọi phép
    kiểm tra quyền theo tư cách thành viên trả về "không phải thành viên" —
    kể cả với chủ tenant."""
    rows = db._fetch_all(
        "SELECT count(*) AS n FROM users u WHERE u.deleted_at IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM tenant_members m "
        "                WHERE m.user_id = u.id AND m.tenant_id = u.tenant_id)")
    assert rows[0]["n"] == 0


def test_admins_were_carried_over_as_admins():
    rows = db._fetch_all(
        "SELECT count(*) AS n FROM users u JOIN tenant_members m "
        "ON m.user_id = u.id AND m.tenant_id = u.tenant_id "
        "WHERE u.is_admin AND m.role <> 'admin'")
    assert rows[0]["n"] == 0, "một quản trị viên bị hạ vai trò khi chuyển sang tenant_members"


def test_the_migration_is_idempotent():
    """Chạy lại `ensure_tables()` không được đẻ thêm một dòng nào.

    Mọi câu backfill dùng `ON CONFLICT DO NOTHING` hoặc `WHERE ... IS NULL`,
    nhưng đó là ý định — test này là bằng chứng.
    """
    def snapshot():
        return {
            t: db._fetch_all(f"SELECT count(*) AS n FROM {t}")[0]["n"]
            for t in ("samples", "signers", "capture_sessions",
                      "vocabulary_groups", "tenant_members", "languages",
                      "classes", "users")
        }

    before = snapshot()
    db.ensure_tables()
    assert snapshot() == before


