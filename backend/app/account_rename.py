"""Đổi tên tài khoản, và kéo theo mọi bản sao của cái tên đó.

Vấn đề
------
`username` không nằm ở một chỗ. Nó được CHÉP vào dữ liệu ngay lúc ghi, ở bảy
cột thuộc năm bảng, cộng thêm một cột trong `dataset/samples.csv` — nguồn sự
thật thật sự, mà Postgres chỉ là bản gương.

Đo ngày 2026-08-09 trên dữ liệu sản xuất:

    samples.user_id        3.860 hàng mang tên hiển thị
    samples.username       1.063 hàng
    raw_uploads.user_id / .username
    signers.display_name   4 hàng

Không có đường nào để đổi tên, nên chưa ai phát hiện: đổi `users.username` mà
không đụng những chỗ kia thì tài khoản mang tên mới còn toàn bộ dữ liệu họ đã
đóng góp vẫn mang tên cũ. Người dùng nhìn vào Thùng rác của mình và thấy tên
người khác.

HAI LOẠI BẢN SAO, và chỉ một loại được cập nhật
------------------------------------------------
Đây là phần dễ làm sai nhất, nên nói thẳng:

**Ảnh chụp TRẠNG THÁI HIỆN TẠI — PHẢI cập nhật.**
`samples.user_id`, `samples.username`, `raw_uploads.user_id`,
`raw_uploads.username`, `signers.display_name`. Chúng trả lời câu hỏi "dữ liệu
này của ai, gọi họ là gì". Câu trả lời đúng là tên HIỆN TẠI.

**Bằng chứng LỊCH SỬ — TUYỆT ĐỐI KHÔNG cập nhật.**
`audit_log.actor_label`, `legal_document_events.actor_label`. Chúng trả lời câu
hỏi "lúc 2 giờ sáng hôm đó, AI đã bấm nút". Sửa chúng theo tên mới là viết lại
lịch sử: một người đổi tên rồi thì dòng kiểm toán cũ sẽ mô tả một người không
tồn tại vào thời điểm đó. Chính vì vậy hai cột này được điền ngay lúc ghi và cố
ý KHÔNG có khoá ngoại tới `users` — xem docstring `app/legal.py` và bảng
`audit_log`.

Ranh giới đó là toàn bộ lý do module này tồn tại thay vì một câu `UPDATE`.

Thứ tự ghi
----------
CSV TRƯỚC, Postgres SAU. `dataset/samples.csv` là nguồn sự thật và Postgres là
bản gương của nó (xem `docs/…` và `app/db.py`: khi kiểm lược đồ thất bại,
`init_db()` xoá sạch bảng rồi dựng lại TỪ TỆP NÀY). Ghi Postgres trước rồi CSV
hỏng nghĩa là lần khởi động sau sẽ lặng lẽ khôi phục tên cũ.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

#: Cột mang bản sao tên hiển thị và PHẢI đi theo khi đổi tên.
#: Mỗi phần tử là (bảng, cột). Danh sách này là nguồn sự thật cho cả hàm đổi tên
#: lẫn bộ test đối chiếu — hai nơi không thể trôi ra khỏi nhau.
STATE_COPIES: tuple[tuple[str, str], ...] = (
    ("samples", "user_id"),
    ("samples", "username"),
    ("raw_uploads", "user_id"),
    ("raw_uploads", "username"),
)

#: Cột mang tên nhưng là BẰNG CHỨNG LỊCH SỬ. Không bao giờ cập nhật.
#: Ở đây để bộ test khẳng định được rằng chúng KHÔNG đổi — một danh sách cấm
#: không ai kiểm thì chỉ là một lời bình luận.
FROZEN_COPIES: tuple[tuple[str, str], ...] = (
    ("audit_log", "actor_label"),
    ("legal_document_events", "actor_label"),
)


class RenameError(RuntimeError):
    def __init__(self, message: str, *, code: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def rename_user(user_id: str, new_username: str) -> Dict[str, Any]:
    """Đổi `users.username` và mọi bản sao trạng thái của nó.

    Trả về số hàng đã đổi ở từng chỗ, để người gọi ghi vào nhật ký kiểm toán và
    để người vận hành thấy việc gì đã thật sự xảy ra.
    """
    from app.storage.metadata_db import _cursor, _fetch_all
    from app.tenant_context import system_scope

    new_username = (new_username or "").strip()
    if not new_username:
        raise RenameError("Tên tài khoản không được để trống.",
                          code="empty_username")
    if len(new_username) > 100:
        raise RenameError("Tên tài khoản quá dài (tối đa 100 ký tự).",
                          code="username_too_long")

    with system_scope("rename: doc tai khoan va kiem trung ten"):
        rows = _fetch_all("SELECT id, username, tenant_id FROM users WHERE id = %s",
                          (str(user_id),))
        if not rows:
            raise RenameError("Không tìm thấy tài khoản.", code="user_not_found",
                              status_code=404)
        old_username = rows[0]["username"]
        tenant_id = rows[0]["tenant_id"]
        if old_username == new_username:
            return {"changed": False, "old_username": old_username,
                    "new_username": new_username, "rows": {}}

        # Trùng tên kiểm Ở ĐÂY chứ không dựa vào ràng buộc UNIQUE bắn lỗi: thông
        # báo của Postgres nói về tên chỉ mục, không nói được với người dùng
        # rằng cái tên họ chọn đã có người lấy.
        clash = _fetch_all(
            "SELECT id FROM users WHERE lower(username) = lower(%s) AND id <> %s",
            (new_username, str(user_id)))
        if clash:
            raise RenameError(f"Tên {new_username!r} đã có người dùng.",
                              code="username_taken", status_code=409)

    # ---- 1. NGUỒN SỰ THẬT: dataset/samples.csv --------------------------
    csv_rows = _rename_in_samples_csv(old_username, new_username)

    # ---- 2. bản gương Postgres ------------------------------------------
    counts: Dict[str, int] = {"samples.csv": csv_rows}
    with system_scope("rename: cap nhat moi ban sao ten hien thi"):
        with _cursor() as cur:
            cur.execute("UPDATE users SET username = %s, updated_at = now() WHERE id = %s",
                        (new_username, str(user_id)))
            counts["users"] = cur.rowcount or 0

            for table, column in STATE_COPIES:
                # Khớp theo `auth_user_id` khi có — đó là DANH TÍNH. Chỉ khớp
                # theo tên cũ cho những hàng không có auth_user_id, vì với chúng
                # cái tên là thứ duy nhất còn lại để nhận ra chủ. Hai người từng
                # trùng tên hiển thị thì hàng vô chủ sẽ đi theo người đổi tên —
                # không tránh được, và đó là hệ quả của việc `user_id` là văn
                # bản tự do chứ không phải khoá.
                #
                # `tenant_id = %s` là BẮT BUỘC và không phải để tối ưu. Khối này
                # chạy trong `system_scope`, nên RLS không lọc gì; không có mệnh
                # đề này thì nhánh `auth_user_id IS NULL` sẽ đổi tên cả hàng vô
                # chủ của tenant KHÁC trùng tên hiển thị. Trên bản triển khai
                # một tenant thì vô hình — đúng kiểu lỗi chỉ lộ ra khi có khách
                # hàng thứ hai.
                cur.execute(
                    f"UPDATE {table} SET {column} = %s "
                    f"WHERE {column} = %s AND tenant_id = %s "
                    f"AND (auth_user_id = %s OR auth_user_id IS NULL)",
                    (new_username, old_username, tenant_id, str(user_id)))
                counts[f"{table}.{column}"] = cur.rowcount or 0

            cur.execute(
                "UPDATE signers SET display_name = %s WHERE external_user_id = %s",
                (new_username, str(user_id)))
            counts["signers.display_name"] = cur.rowcount or 0

    _rename_in_signers_csv(str(user_id), new_username)

    logger.info("[RENAME] %s: %r -> %r; %s", user_id, old_username, new_username, counts)
    return {"changed": True, "old_username": old_username,
            "new_username": new_username, "rows": counts}


def _rename_in_samples_csv(old_username: str, new_username: str) -> int:
    """Đổi cột `user_id` trong `dataset/samples.csv`. Trả về số dòng đã đổi.

    Ghi qua tệp tạm rồi `os.replace`, giống `ensure_samples_column`: tệp này là
    nguồn sự thật và một bản cụt thì không khôi phục lại được từ Postgres.
    """
    import csv
    import os
    import tempfile

    from app.dataset_samples import SAMPLES_CSV

    if not SAMPLES_CSV.exists():
        return 0

    with open(SAMPLES_CSV, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    if "user_id" not in fieldnames:
        return 0

    changed = 0
    for row in rows:
        if (row.get("user_id") or "") == old_username:
            row["user_id"] = new_username
            changed += 1
    if not changed:
        return 0

    fd, tmp_path = tempfile.mkstemp(dir=str(SAMPLES_CSV.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_path, SAMPLES_CSV)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return changed


def _rename_in_signers_csv(user_id: str, new_username: str) -> None:
    """`signers.csv` cũng giữ `display_name`, và nó cũng là tệp nguồn."""
    try:
        from filelock import FileLock

        from app import signers as signers_mod

        lock = FileLock(str(signers_mod.SIGNERS_CSV) + ".lock")
        with lock:
            rows = signers_mod._load_rows_locked()
            touched = False
            for row in rows:
                if (row.get("external_user_id") or "").strip() == user_id:
                    row["display_name"] = new_username
                    touched = True
            if touched:
                signers_mod._write_rows_locked(rows)
    except Exception as exc:
        # Không làm hỏng việc đổi tên vì bản gương tệp: Postgres đã đúng, và
        # `signers.csv` được đồng bộ lại được. Ghi log đủ to để thấy.
        logger.warning("[RENAME] signers.csv khong cap nhat duoc cho %s: %s",
                       user_id, exc)


def find_stale_display_names() -> Dict[str, int]:
    """Đếm những hàng còn mang tên KHÔNG khớp tên hiện tại của chủ tài khoản.

    Dùng cho kiểm tra sau triển khai. Khác 0 nghĩa là có một lần đổi tên nào đó
    đã không kéo theo dữ liệu — hoặc dữ liệu được ghi bằng một đường vòng qua
    hàm này.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    out: Dict[str, int] = {}
    with system_scope("rename: soat ten hien thi lac hau"):
        for table, column in STATE_COPIES:
            rows = _fetch_all(
                f"SELECT count(*) AS n FROM {table} t JOIN users u ON u.id = t.auth_user_id "
                f"WHERE t.{column} IS NOT NULL AND t.{column} <> '' AND t.{column} <> u.username")
            out[f"{table}.{column}"] = int(rows[0]["n"]) if rows else 0
    return out
