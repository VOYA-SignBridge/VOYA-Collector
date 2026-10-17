"""Ánh xạ `storage_key` (khoá trên đĩa) -> đường dẫn trên Google Drive.

Vì sao tách khoá trên đĩa khỏi đường dẫn Drive
---------------------------------------------
Trước 18/10/2026 hai thứ là một: task tải lên dùng thẳng `storage_key` làm đường
dẫn Drive. Muốn Drive xếp theo tổ chức (`tenants/<id>/…`) mà đổi luôn khoá trên
đĩa thì phải viết lại DB (4.806 mẫu), samples.csv, ~4.900 sidecar, 7.337 tệp
split — trong đó có split nghiên cứu ĐÓNG BĂNG bằng sha256 — và gói SOT (sot-init
áp lại gói mỗi lần `compose up`, giá trị trong gói thắng giá trị ở DB).

Nhưng không chỗ nào ĐỌC Drive theo đường dẫn: tải về đi theo `storage_url` (ID
tệp). Nên chỉ cần ánh xạ ở tầng ghi lên Drive; khoá trên đĩa giữ nguyên.

Hai bố cục (`GDRIVE_LAYOUT`)
---------------------------

    legacy   Drive soi đúng cây trên đĩa. MẶC ĐỊNH — triển khai mã này không dời gì.
    tenant   tenants/<id>/{features,raw,raw_videos,models}/…

Chỉ bật `tenant` SAU KHI đã dời dữ liệu cũ trên Drive sang cây mới: với `tenant`,
đổi tên/xoá lớp tìm thư mục ở chỗ mới, nên thư mục còn nằm ở chỗ cũ sẽ bị bỏ sót.
Và `models/<tên>/latest_manifest.json` là đường dẫn CỐ ĐỊNH mà app di động đọc —
phải cập nhật app trước.

Cây nào mang tenant ở đâu
------------------------
`features/` và `raw/` (kho raw là gương của features) đã phân vùng trên đĩa:
tenant gốc ở ngay gốc cây, tenant khác ở `_tenants/<id>/` (xem
`dataset_manager.tenant_features_root`). Tenant đọc được từ chính khoá.

`raw_videos/` và `models/` KHÔNG phân vùng trên đĩa, nên người gọi phải đưa tenant.
Thiếu thì TỪ CHỐI chứ không rơi về `default`: `normalize_tenant_id("")` trả về
"default", và rơi-về im lặng chính là cách dữ liệu của tổ chức X chui vào cây
của nền tảng.

Mọi thứ khác (SOT/, CSV soi, Sheets ở gốc Drive) không phải dữ liệu của tenant và
đi qua nguyên vẹn ở mọi bố cục.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Optional

from app.tenancy import DEFAULT_TENANT_ID, is_valid_tenant_id

LEGACY = "legacy"
TENANT = "tenant"
LAYOUTS = (LEGACY, TENANT)

#: Gốc cây theo tổ chức trên Drive.
TENANTS_ROOT = "tenants"
#: Thư mục phân vùng bên trong cây trên đĩa (trùng `dataset_manager.TENANT_PARTITION_DIRNAME`).
PARTITION_DIRNAME = "_tenants"
#: Cây đã phân vùng trên đĩa — tenant nằm trong khoá.
PARTITIONED_TREES = ("features", "raw")
#: Cây không phân vùng trên đĩa — tenant phải do người gọi đưa.
UNPARTITIONED_TREES = ("raw_videos", "models")
TENANT_TREES = PARTITIONED_TREES + UNPARTITIONED_TREES


def current_layout() -> str:
    from app.config import settings

    layout = str(getattr(settings, "gdrive_layout", LEGACY) or LEGACY).strip().lower()
    if layout not in LAYOUTS:
        raise ValueError(f"GDRIVE_LAYOUT={layout!r} không hợp lệ; chỉ nhận {LAYOUTS}")
    return layout


def _check_tenant(tenant_id: Any) -> Optional[str]:
    """None = người gọi không đưa. Có đưa thì phải là id hợp lệ — KHÔNG chuẩn hoá
    "" thành "default" (xem docstring module)."""
    if tenant_id is None:
        return None
    if not isinstance(tenant_id, str):
        raise TypeError(f"tenant_id phải là str hoặc None, nhận {type(tenant_id).__name__}: {tenant_id!r}")
    if not is_valid_tenant_id(tenant_id):
        raise ValueError(f"tenant_id không hợp lệ: {tenant_id!r}")
    return tenant_id


def _split_key(storage_key: str) -> list[str]:
    if not isinstance(storage_key, str):
        raise TypeError(f"storage_key phải là str, nhận {type(storage_key).__name__}")
    parts = [p for p in storage_key.replace("\\", "/").strip().strip("/").split("/") if p != ""]
    if not parts:
        raise ValueError("storage_key rỗng")
    if any(p in (".", "..") for p in parts):
        raise ValueError(f"storage_key chứa '.'/'..': {storage_key!r}")
    return parts


def drive_path_for(storage_key: str, tenant_id: Optional[str] = None, *, layout: Optional[str] = None) -> str:
    """Đường dẫn trên Drive (tương đối với thư mục gốc Drive) cho một khoá trên đĩa.

    `tenant_id` bắt buộc với `raw_videos/` và `models/` ở bố cục `tenant`; với
    `features/`/`raw/` thì tuỳ chọn, nhưng nếu có thì phải khớp tenant trong khoá.
    Idempotent: đưa vào một đường dẫn đã ánh xạ thì nhận lại chính nó.
    """
    layout = layout or current_layout()
    if layout not in LAYOUTS:
        raise ValueError(f"GDRIVE_LAYOUT={layout!r} không hợp lệ; chỉ nhận {LAYOUTS}")
    tenant = _check_tenant(tenant_id)
    parts = _split_key(storage_key)

    if parts[0] == TENANTS_ROOT:
        # Đã ở bố cục tenant (task retry, migration chạy lại) -> giữ nguyên.
        if len(parts) < 3 or not is_valid_tenant_id(parts[1]) or parts[2] not in TENANT_TREES:
            raise ValueError(f"đường dẫn tenants/ không hợp lệ: {storage_key!r}")
        if tenant is not None and tenant != parts[1]:
            raise ValueError(f"tenant của đường dẫn ({parts[1]}) khác tenant được đưa ({tenant})")
        return "/".join(parts)

    tree = parts[0]
    if tree not in TENANT_TREES:
        return "/".join(parts)  # SOT/, CSV soi, Sheets… — không phải dữ liệu tenant

    rest = parts[1:]
    if tree in PARTITIONED_TREES:
        if rest and rest[0] == PARTITION_DIRNAME:
            if len(rest) < 2 or not is_valid_tenant_id(rest[1]):
                raise ValueError(f"phân vùng _tenants/ không hợp lệ trong {storage_key!r}")
            key_tenant, rest = rest[1], rest[2:]
        else:
            key_tenant = DEFAULT_TENANT_ID  # cây gốc trên đĩa là của tenant gốc
        if tenant is not None and tenant != key_tenant:
            raise ValueError(
                f"{storage_key!r} thuộc tenant {key_tenant} theo bố cục trên đĩa, nhưng được đưa tenant {tenant}")
        tenant = key_tenant
    elif tenant is None and layout == TENANT:
        raise ValueError(f"{tree}/ không phân vùng trên đĩa — phải đưa tenant_id cho {storage_key!r}")

    if layout == LEGACY:
        return "/".join(parts)
    return str(PurePosixPath(TENANTS_ROOT, tenant, tree, *rest))
