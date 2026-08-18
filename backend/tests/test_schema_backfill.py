"""Backfill: chuyển đúng, và những chỗ CỐ Ý để trống thì phải còn trống.

Tách từ `test_schema_v3.py` (593 dòng, bốn mối quan tâm không liên quan gộp
chung). Bối cảnh đầy đủ của đợt vá lược đồ: `docs/02-data/SAAS_SCHEMA_DESIGN.md`
§9sexies.
"""

from __future__ import annotations


from pathlib import Path

import pytest

from app.storage import metadata_db as db


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()

# --------------------------------------------------------------- backfill

#: Các tenant tổng hợp do bộ đo cách ly dựng ra. Hàng của chúng được tạo SAU đợt
#: backfill và cố ý không đi qua nó — mẫu của chúng chỉ cần tồn tại để bị thử
#: đọc/ghi xuyên tổ chức, nên không ai gán phiên thu cho chúng.
#:
#: Không loại chúng ra thì các phép kiểm dưới đây đổi ý nghĩa: từ *"đợt backfill
#: có bỏ sót hàng nào không"* thành *"có bộ đo nào vừa chạy trước không"*, và
#: chúng đỏ theo thứ tự chạy chứ không theo mã.
#: Dấu `%` phải viết ĐÔI. `_fetch_all` khai `params: tuple = ()` rồi vẫn truyền
#: tuple rỗng ấy vào `cur.execute(sql, params)`, nên psycopg luôn chạy bước nội
#: suy và một `%` đơn thành ô giữ chỗ không có đối số — báo `IndexError: tuple
#: index out of range`, một thông điệp không nhắc gì tới LIKE và dễ bị đọc nhầm
#: thành lỗi dữ liệu. `\_` là gạch dưới theo nghĩa đen, vì không có nó thì `_`
#: là ký tự đại diện một ký tự bất kỳ và mệnh đề sẽ loại nhầm cả tenant khác.
TENANT_TONG_HOP = "tenant_id NOT LIKE 'iso\\_%%'"


def test_every_sample_with_a_real_session_id_got_linked():
    """2.863 mẫu có `session_id` thật, và không một mẫu nào trong số đó được
    phép còn treo sau backfill."""
    rows = db._fetch_all(
        "SELECT count(*) AS n FROM samples "
        "WHERE session_id IS NOT NULL AND session_id <> '' "
        "  AND capture_session_id IS NULL "
        f"  AND {TENANT_TONG_HOP}")
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
    # Giữ nguyên độ chặt — KHÔNG loại tenant tổng hợp ở đây. Một tài khoản sống
    # thiếu tư cách thành viên là lỗi thật dù nó nằm ở tenant nào, và phép đo
    # cách ly mất đối chứng dương nếu tài khoản gieo bị coi là "không phải thành
    # viên". Chỉ đổi phần BÁO CÁO: liệt kê đích danh, vì bản cũ chỉ trả về một
    # con số và người đọc phải tự đi truy xem hàng nào — lượt chạy 18/08/2026
    # đỏ đúng một hàng và mất thêm một vòng chẩn đoán chỉ để biết đó là ai.
    rows = db._fetch_all(
        "SELECT u.username, u.tenant_id, u.created_at FROM users u "
        "WHERE u.deleted_at IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM tenant_members m "
        "                WHERE m.user_id = u.id AND m.tenant_id = u.tenant_id) "
        "ORDER BY u.created_at DESC")
    assert not rows, (
        "tai khoan song thieu tu cach thanh vien trong chinh tenant cua no: "
        + "; ".join(f"{r['username']}@{r['tenant_id']} (tao {r['created_at']})"
                    for r in rows))


def test_kich_ban_gieo_fixture_do_luong_luon_gan_tu_cach_thanh_vien():
    """Lưới bắt hồi quy cho `scripts/seed_isolation_fixture.py`.

    Ngày 15/08/2026 kịch bản ấy gieo ba tài khoản sống — `iso_user_a`,
    `iso_user_b`, `perf_user` — với `users.tenant_id` nhưng KHÔNG có dòng
    `memberships` nào, và làm bài kiểm ngay bên trên đỏ.

    Vì sao cần lưới ở TẦNG NGUỒN chứ không chỉ bất biến ở tầng dữ liệu
    ------------------------------------------------------------------
    Bài kiểm bên trên chỉ đỏ SAU KHI có người chạy kịch bản. Giữa lúc thêm một
    tài khoản gieo thứ tư và lúc ai đó chạy lại kịch bản có thể là hàng tuần, và
    khi nó đỏ thì nó trỏ vào dữ liệu chứ không trỏ vào dòng mã đã gây ra.

    Phép kiểm này cố tình HẸP: nó chỉ đếm, không cố hiểu luồng. Đổi lại nó không
    cần cơ sở dữ liệu và không cần chạy kịch bản.
    """
    import re

    nguon = (Path(__file__).resolve().parents[2]
             / "scripts" / "seed_isolation_fixture.py").read_text(encoding="utf-8")
    than = "\n".join(d for d in nguon.splitlines()
                     if not d.lstrip().startswith("#"))

    tao = len(re.findall(r"^\s+_tao_user\(", than, re.MULTILINE))
    gan = len(re.findall(r"^\s+_gan_tu_cach_thanh_vien\(", than, re.MULTILINE))

    assert tao > 0, "khong tim thay cho goi _tao_user — phep kiem nay da lac huong"
    assert gan >= tao, (
        f"kich ban gieo {tao} tai khoan nhung chi gan {gan} tu cach thanh vien. "
        f"Mot tai khoan song thieu `memberships` bi he thong coi la 'khong phai "
        f"thanh vien' o moi phep kiem quyen — va phep do co lap mat doi chung "
        f"DUONG, nen ca am xanh khong con chung minh duoc gi.")


def test_admins_were_carried_over_as_admins():
    # Loại tenant tổng hợp: `iso_admin_a` mang cờ `is_admin` nhưng được gieo với
    # vai `editor` một cách CỐ Ý — bộ đo cách ly cần một tài khoản có cờ quản trị
    # nền tảng mà vai trong tenant lại không đủ quyền, để tách bạch hai câu hỏi
    # "có phải quản trị nền tảng không" và "có quyền trong tenant này không".
    # Đó là đối tượng đo, không phải một lần hạ vai do backfill làm sai.
    rows = db._fetch_all(
        "SELECT u.username, u.tenant_id, m.role FROM users u JOIN tenant_members m "
        "ON m.user_id = u.id AND m.tenant_id = u.tenant_id "
        "WHERE u.is_admin AND m.role <> 'admin' "
        f"  AND u.{TENANT_TONG_HOP}")
    assert not rows, (
        "mot quan tri vien bi ha vai tro khi chuyen sang tenant_members: "
        + "; ".join(f"{r['username']}@{r['tenant_id']} -> {r['role']}" for r in rows))


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


