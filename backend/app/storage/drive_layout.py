"""Ánh xạ `storage_key` (khoá trên đĩa) -> đường dẫn trên Google Drive.

Thiết kế đầy đủ: docs/02-data/DRIVE_STORAGE_AND_LOOKUP_LIST.md.

Vì sao tách khoá trên đĩa khỏi đường dẫn Drive
---------------------------------------------
Trước 18/10/2026 hai thứ là một: task tải lên dùng thẳng `storage_key` làm đường
dẫn Drive. Muốn Drive xếp theo tổ chức mà đổi luôn khoá trên đĩa thì phải viết
lại DB (4.806 mẫu), samples.csv, ~4.900 sidecar, 7.337 tệp split — trong đó có
split nghiên cứu ĐÓNG BĂNG bằng sha256 — và gói SOT (sot-init áp lại gói mỗi lần
`compose up`, giá trị trong gói thắng giá trị ở DB).

Nhưng không chỗ nào ĐỌC Drive theo đường dẫn: tải về đi theo `storage_url` (ID
tệp). Nên chỉ cần ánh xạ ở tầng ghi lên Drive; khoá trên đĩa giữ nguyên.

Hai bố cục (`GDRIVE_LAYOUT`)
---------------------------

    legacy   Drive soi đúng cây trên đĩa. MẶC ĐỊNH — triển khai mã này không dời gì.
    tenant   Community/{Samples,Videos,Models}/…            tổ chức cộng đồng (VOYA)
             Tenants/<slug>/{Samples,Videos,Models}/…       mọi tổ chức khác

Tên trên Drive là tiếng Anh, khác tên trên đĩa (`features` -> `Samples`,
`raw_videos` -> `Videos`); bảng đổi là `DRIVE_TREE_NAMES`. Thư mục của tổ chức
mang `tenants.slug` chứ không mang `tenant_id`: tổ chức lập trước 18/10/2026 có
id kèm hậu tố ngẫu nhiên (`truong-b-a9690c`) mà 30+ khoá ngoại khoá cứng, còn
`slug` thì làm sạch được.

Chỉ bật `tenant` SAU KHI đã dời dữ liệu cũ trên Drive sang cây mới
(scripts/drive_tenant_layout_migrate.py): với `tenant`, đổi tên/xoá lớp tìm thư
mục ở chỗ mới, nên thư mục còn nằm ở chỗ cũ sẽ bị bỏ sót.

Cây nào mang tenant ở đâu
------------------------
`features/` và `raw/` (kho raw là gương của features) đã phân vùng trên đĩa:
tenant gốc ở ngay gốc cây, tenant khác ở `_tenants/<id>/` (xem
`dataset_manager.tenant_features_root`). Tenant đọc được từ chính khoá.

`raw_videos/` và `models/` KHÔNG phân vùng trên đĩa, nên người gọi phải đưa tenant.
Thiếu thì TỪ CHỐI chứ không rơi về `default`: `normalize_tenant_id("")` trả về
"default", và rơi-về im lặng chính là cách dữ liệu của tổ chức X chui vào cây
của nền tảng.

Mọi thứ khác (SOT/, Sheets ở gốc Drive) không phải dữ liệu của tenant và đi qua
nguyên vẹn ở mọi bố cục.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Dict, Optional

from app.tenancy import DEFAULT_TENANT_ID, is_valid_tenant_id

LEGACY = "legacy"
TENANT = "tenant"
LAYOUTS = (LEGACY, TENANT)

#: Thư mục phân vùng bên trong cây trên đĩa (trùng `dataset_manager.TENANT_PARTITION_DIRNAME`).
PARTITION_DIRNAME = "_tenants"
#: Tên các cây dữ liệu TRÊN ĐĨA — dùng các hằng này, đừng gõ lại chuỗi ở nơi khác.
FEATURES_TREE = "features"
RAW_TREE = "raw"
RAW_VIDEOS_TREE = "raw_videos"
MODELS_TREE = "models"
#: Cây đã phân vùng trên đĩa — tenant nằm trong khoá.
PARTITIONED_TREES = (FEATURES_TREE, RAW_TREE)
#: Cây không phân vùng trên đĩa — tenant phải do người gọi đưa.
UNPARTITIONED_TREES = (RAW_VIDEOS_TREE, MODELS_TREE)
TENANT_TREES = PARTITIONED_TREES + UNPARTITIONED_TREES

#: Tên trên DRIVE (bố cục `tenant`).
COMMUNITY_ROOT = "Community"
TENANTS_ROOT = "Tenants"
LOOKUP_LIST_DIRNAME = "Lookup list"
DRIVE_TREE_NAMES: Dict[str, str] = {
    FEATURES_TREE: "Samples",
    RAW_TREE: "Raw",
    RAW_VIDEOS_TREE: "Videos",
    MODELS_TREE: "Models",
}
#: Bố cục tenant đời đầu (chạy sáng 18/10/2026): `tenants/<tenant_id>/<cây trên đĩa>/…`.
#: Còn nhận làm đầu vào để task xếp hàng từ trước vẫn đi đúng chỗ mới.
OLD_TENANTS_ROOT = "tenants"

#: Tiền tố tên Sheet Lookup list của VOYA và của nền tảng (`community - Labels`,
#: `platform - Tenants`).
COMMUNITY_PREFIX = "community"
PLATFORM_PREFIX = "platform"
#: Các Sheet trong `Lookup list/` của mỗi tổ chức, theo thứ tự hiện trên Drive.
#: Tên tệp là `<tiền tố> - <loại>`, tên tab là loại viết thường.
SHEET_LABELS = "Labels"
SHEET_SAMPLES = "Samples"
SHEET_VIDEOS = "Videos"
SHEET_DATASET_VERSIONS = "Dataset versions"
SHEET_MODELS = "Models"
SHEET_AUDIT_LOGS = "Audit logs"
TENANT_SHEETS = (SHEET_LABELS, SHEET_SAMPLES, SHEET_VIDEOS, SHEET_DATASET_VERSIONS,
                 SHEET_MODELS, SHEET_AUDIT_LOGS)
#: Các Sheet trong `Lookup list/` ở gốc Drive (chỉ quản trị nền tảng).
SHEET_TENANTS = "Tenants"
SHEET_STORAGE_LAYOUT = "Storage layout"
PLATFORM_SHEETS = (SHEET_TENANTS, SHEET_STORAGE_LAYOUT)


def sheet_title(prefix: str, sheet_type: str) -> str:
    return f"{prefix} - {sheet_type}"


#: Tên không tổ chức nào được mang: Sheet hay thư mục của nó sẽ trùng tên với
#: của hệ thống. `tenant_admin` đọc danh sách này, đừng chép lại ở đó.
RESERVED_NAMES = (COMMUNITY_PREFIX, PLATFORM_PREFIX, COMMUNITY_ROOT, TENANTS_ROOT, LOOKUP_LIST_DIRNAME)


def current_layout() -> str:
    from app.config import settings

    layout = str(getattr(settings, "gdrive_layout", LEGACY) or LEGACY).strip().lower()
    if layout not in LAYOUTS:
        raise ValueError(f"GDRIVE_LAYOUT={layout!r} không hợp lệ; chỉ nhận {LAYOUTS}")
    return layout


# ------------------------------------------------------------- thư mục của tổ chức

_tenant_root_cache: Dict[str, str] = {}


def clear_tenant_root_cache() -> None:
    """Sau khi đổi `tenants.slug` trong cùng tiến trình (script dời Drive)."""
    _tenant_root_cache.clear()


def tenant_drive_root(tenant_id: str) -> str:
    """`Community` cho tổ chức cộng đồng, `Tenants/<slug>` cho tổ chức khác.

    Đọc `tenants` một lần mỗi tổ chức mỗi tiến trình, DƯỚI phạm vi hiện hành:
    RLS cho mỗi tổ chức thấy dòng của chính nó, và task toàn nền tảng chạy trong
    `system_scope`. Không thấy dòng thì TỪ CHỐI — đoán một thư mục là cách dữ
    liệu rơi vào chỗ không ai tìm.
    """
    if tenant_id in _tenant_root_cache:
        return _tenant_root_cache[tenant_id]
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all("SELECT slug, tenant_type FROM tenants WHERE tenant_id = %s", (tenant_id,))
    if not rows:
        raise ValueError(f"không thấy tổ chức {tenant_id!r} (trong phạm vi hiện hành) để ánh xạ thư mục Drive")
    if (rows[0].get("tenant_type") or "").upper() == "COMMUNITY":
        root = COMMUNITY_ROOT
    else:
        slug = (rows[0].get("slug") or tenant_id).strip()
        if not is_valid_tenant_id(slug):
            raise ValueError(f"slug không hợp lệ cho thư mục Drive của {tenant_id!r}: {slug!r}")
        root = f"{TENANTS_ROOT}/{slug}"
    _tenant_root_cache[tenant_id] = root
    return root


# ------------------------------------------------------------- ánh xạ


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


def _already_mapped(parts: list[str], tenant: Optional[str], storage_key: str) -> Optional[str]:
    """Đường dẫn đã ở bố cục mới (task retry, migration chạy lại) -> giữ nguyên."""
    drive_trees = DRIVE_TREE_NAMES.values()
    if parts[0] == COMMUNITY_ROOT:
        if len(parts) < 2 or parts[1] not in drive_trees:
            raise ValueError(f"đường dẫn {COMMUNITY_ROOT}/ không hợp lệ: {storage_key!r}")
        prefix = COMMUNITY_ROOT
    elif parts[0] == TENANTS_ROOT:
        if len(parts) < 3 or not is_valid_tenant_id(parts[1]) or parts[2] not in drive_trees:
            raise ValueError(f"đường dẫn {TENANTS_ROOT}/ không hợp lệ: {storage_key!r}")
        prefix = f"{TENANTS_ROOT}/{parts[1]}"
    else:
        return None
    if tenant is not None and tenant_drive_root(tenant) != prefix:
        raise ValueError(f"{storage_key!r} không nằm trong thư mục của tenant {tenant}")
    return "/".join(parts)


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

    mapped = _already_mapped(parts, tenant, storage_key)
    if mapped is not None:
        return mapped

    if parts[0] == OLD_TENANTS_ROOT:
        if len(parts) < 3 or not is_valid_tenant_id(parts[1]) or parts[2] not in TENANT_TREES:
            raise ValueError(f"đường dẫn {OLD_TENANTS_ROOT}/ không hợp lệ: {storage_key!r}")
        if tenant is not None and tenant != parts[1]:
            raise ValueError(f"tenant của đường dẫn ({parts[1]}) khác tenant được đưa ({tenant})")
        if layout == LEGACY:
            return "/".join(parts)
        return str(PurePosixPath(tenant_drive_root(parts[1]), DRIVE_TREE_NAMES[parts[2]], *parts[3:]))

    tree = parts[0]
    if tree not in TENANT_TREES:
        return "/".join(parts)  # SOT/, Sheets… — không phải dữ liệu tenant

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
    return str(PurePosixPath(tenant_drive_root(tenant), DRIVE_TREE_NAMES[tree], *rest))
