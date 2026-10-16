"""Mặt phẳng phân quyền: PostgreSQL giữ dữ liệu, Casbin quyết định.

Đọc theo thứ tự này
-------------------
    catalog.py               quyền nào tồn tại, role dựng sẵn gồm những gì
    seed.py                  đưa danh mục đó vào cơ sở dữ liệu
    adapter.py               chiếu bảng RBAC → policy Casbin (CHỈ ĐỌC)
    enforcer.py              vòng đời enforcer, nạp lại, hỏng-thì-đóng
    scope_resolver.py        đối tượng nghiệp vụ → chuỗi domain
    authorization_service.py MỘT cửa: authorize() / require()
    passcode.py             xác thực nâng cấp, chạy SAU khi đã ALLOW
    policy_invalidator.py    làm sao các tiến trình khác biết policy đã đổi

Schema nằm ở `app/storage/authz_schema.py`, backfill ở
`app/cli/backfill_authz.py`, tài liệu ở `docs/03-security/AUTHORIZATION.md`.

Bốn ranh giới đừng làm mờ
--------------------------
    RLS            dòng này ai được CHẠM tới?            storage/rls.py
    Composite FK   quan hệ này có được phép TỒN TẠI?     storage/authz_schema.py
    Casbin         chủ thể có NĂNG LỰC nghiệp vụ này?    authorization_service.py
    Passcode       đúng là người này đang ngồi đây?      passcode.py

Bốn câu hỏi khác nhau. Không cái nào thay được cái nào, và trộn hai cái vào
một chỗ là cách chắc chắn nhất để mất cả hai.

Vì sao gói này KHÔNG import gì ở mức module
--------------------------------------------
`adapter.py` import `casbin`. Nếu `__init__` kéo nó vào ngay, thì mọi thứ chạm
tới gói này — kể cả `seed.py`, vốn chỉ ghi danh mục quyền vào cơ sở dữ liệu —
sẽ đòi thư viện Casbin phải có mặt.

Đó là ràng buộc sai chiều. Schema và danh mục quyền là nền móng: chúng phải cài
được trên một bản triển khai chạy `AUTHZ_MODE=legacy`, nơi Casbin cố ý không
được cài. Và vì `ensure_tables()` gọi seed bên trong `_run_ddl` — nơi nuốt lỗi —
một `ImportError` ở đó sẽ không làm gì ầm ĩ cả: nó chỉ lặng lẽ để lại một cơ sở
dữ liệu không có role dựng sẵn nào, và triệu chứng hiện ra rất xa nguồn.

Nên các tên dưới đây được phân giải LƯỜI qua `__getattr__` (PEP 562):
`from app.authorization import PERM` vẫn chạy mà không cần Casbin, còn
`from app.authorization import require` thì cần — đúng như phải thế.
"""

from typing import Any

__all__ = ["authorize", "require", "Decision", "AuthorizationError", "PERM", "Target"]

#: Tên công khai → module thật sự định nghĩa nó.
_LAZY = {
    "authorize": "app.authorization.authorization_service",
    "require": "app.authorization.authorization_service",
    "Decision": "app.authorization.authorization_service",
    "AuthorizationError": "app.authorization.authorization_service",
    "PERM": "app.authorization.catalog",
    "Target": "app.authorization.scope_resolver",
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(target), name)


def __dir__() -> list[str]:
    return sorted(__all__)
