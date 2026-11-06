"""Thư mục sandbox trên Drive cho các ca SOT cần Drive thật. Chỉ đụng đúng thư mục này.

    python drive_sandbox.py tao <tên>    in id của thư mục vừa tạo
    python drive_sandbox.py xoa <tên>    xoá rồi kiểm lại là đã mất

Tên phải bắt đầu bằng `_KIEM_THU_`: script từ chối mọi thứ khác, vì `delete_path` trên
gốc Drive dùng chung mà sai tên là xoá dữ liệu thật.
"""

from __future__ import annotations

import sys

from app.storage.gdrive_client import get_gdrive_client

TIEN_TO = "_KIEM_THU_"


def main() -> None:
    lenh, ten = sys.argv[1], sys.argv[2]
    if not ten.startswith(TIEN_TO) or "/" in ten:
        sys.exit(f"TU CHOI: '{ten}' khong phai thu muc sandbox.")
    client = get_gdrive_client()
    if lenh == "tao":
        print("SANDBOX_ID=" + client.ensure_path(ten))
    elif lenh == "xoa":
        client.delete_path(ten)
        # Hỏi thẳng Drive: `resolve_folder_path` đọc `_folder_cache` và trả id đã xoá.
        q = f"name = '{ten}' and '{client.root_folder_id}' in parents and trashed = false"
        con_lai = client.service.files().list(
            q=q, fields="files(id)", supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute().get("files")
        print("SANDBOX_CON=" + ("co" if con_lai else "khong"))
    else:
        sys.exit(f"lenh la: {lenh}")


if __name__ == "__main__":
    main()
