"""Bản xuất CỦA MỘT NGƯỜI — "cho tôi tệp của chính tôi", chạy nền.

Khác `tenant_lifecycle` (xuất/xoá cho một TỔ CHỨC rời nền tảng, chỉ quản trị
viên gọi được, mang cổng đồng thuận theo `export_purpose` vì gói có thể đi ra
ngoài tổ chức) ở đúng một điểm nhưng điểm đó đổi hết phần còn lại: người gọi
chỉ xin lại dữ liệu CỦA CHÍNH HỌ. Không cổng đồng thuận nào cần áp — một người
xem lại thứ họ vừa đóng góp không phải phát hành cho bên thứ ba, cùng lý do
nhánh "hoàn trả" của `tenant_lifecycle._ten_tep_duoc_phep` không lọc theo kiểm
duyệt hay đồng thuận.

Gói gồm hai phần, không chỉ metadata:

    samples.csv   đúng các cột của `dataset/samples.csv`, chỉ những dòng
                  `auth_user_id` khớp người gọi
    files/*.npz   tệp đặc trưng thật của đúng các dòng đó

`portable_export` kiểm tra đường dẫn chính xác trong tenant, checksum và NPZ;
gói dùng đường dẫn tương đối, kèm JSON, nhãn và manifest cho máy nhận.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PersonalExportError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _export_root() -> Path:
    from app.config import settings

    root = Path(settings.dataset_root) / "_exports" / "personal"
    root.mkdir(parents=True, exist_ok=True)
    return root


def request_export(tenant_id: str, user_id: str) -> Dict[str, Any]:
    """Ghi nhận yêu cầu và trả về ngay. Việc nặng do tác vụ nền làm.

    KHÔNG bọc `system_scope`, khác `tenant_lifecycle.request_export`. Hàm đó
    cần vì `tenant_id` của nó là một THAM SỐ ĐƯỜNG DẪN — quản trị viên nền
    tảng có thể đang đứng ở tenant X mà xuất cho tenant Y, nên tenant ghi vào
    hàng không khớp phạm vi hiện hành. Ở đây `tenant_id` LUÔN là kết quả của
    `require_tenant()` phía router — tức đúng phạm vi phiên đang có — nên câu
    INSERT dưới đây đã khớp `WITH CHECK` của RLS mà không cần mở rộng gì.
    """
    from app.config import settings
    from app.storage.metadata_db import _execute
    from app.modules.saas.tenancy import normalize_tenant_id

    tenant = normalize_tenant_id(tenant_id)
    export_id = str(uuid.uuid4())
    ttl_days = int(getattr(settings, "tenant_export_ttl_days", 14) or 14)
    expires = datetime.now(timezone.utc) + timedelta(days=ttl_days)

    _execute(
        "INSERT INTO personal_exports(export_id, tenant_id, user_id, status, expires_at) "
        "VALUES(%s, %s, %s, 'pending', %s)",
        (export_id, tenant, str(user_id), expires),
    )
    logger.info("[PERSONAL_EXPORT] %s yeu cau xuat du lieu cua chinh minh o %s",
                user_id, tenant)
    return {"export_id": export_id, "tenant_id": tenant, "status": "pending"}


def _owned_rows(tenant: str, user_id: str) -> List[Dict[str, str]]:
    from app.modules.dataset.samples import list_samples

    uid = str(user_id)
    return [r for r in list_samples(tenant) if str(r.get("auth_user_id") or "") == uid]


def _readme(tenant: str, sample_count: int, file_count: int) -> str:
    lines = [
        "Bản xuất dữ liệu CỦA BẠN.",
        f"Tổ chức: {tenant}",
        f"Thời điểm: {datetime.now(timezone.utc).isoformat()}",
        f"Số mẫu: {sample_count}",
        f"Số tệp đặc trưng đính kèm: {file_count}",
        "",
        "samples.csv   — đúng các cột của kho dữ liệu, chỉ dòng của bạn.",
        "samples.json  — cùng các mẫu với CSV; đường dẫn tương đối tính từ thư mục giải nén.",
        "files/*.npz   — đầy đủ tệp đặc trưng; thiếu/hỏng tệp thì không công bố gói.",
        "labels.json   — metadata danh mục của các nhãn trong gói.",
        "manifest.json — SHA-256, feature_dim và class_uid_to_target_idx liên tục từ 0.",
        "",
        "Trên máy khác: cài cùng phiên bản repo và dependencies của pipeline train.",
        "Nạp bằng processed.train_utils.dataset_loader.NPZSignDataset(",
        "  '<export>/samples.csv', root='<export>',",
        "  class_uid_to_target_idx=<mapping trong manifest>, to_tensor=True).",
        "Không cần database/Drive của máy nguồn để nạp NPZ đã xuất.",
        "Chia train/val/test theo signer/session trước khi train; không dùng chung",
        "một lần quay hay bản augment của nó ở các split khác nhau.",
        "Gói không tự tạo split và không đảm bảo đủ nhãn/người ký cho nghiên cứu.",
        "",
        "Gói này chỉ chứa dữ liệu bạn đã tự đóng góp. Nó không phải bản phát hành",
        "và không nên dùng để chia sẻ lại nếu bạn chưa xin phép tổ chức.",
    ]
    return "\n".join(lines) + "\n"


def run_export(export_id: str) -> Dict[str, Any]:
    """Dựng gói zip cho một yêu cầu. Chạy trong tác vụ nền.

    Cùng khuôn với `tenant_lifecycle.run_export`: ghi ra `.part` rồi mới đổi
    tên, để một tiến trình bị giết giữa chừng không để lại một tệp mang đúng
    tên thật nhưng nội dung hỏng.
    """
    import zipfile

    from app.config import settings
    from app.modules.dataset.catalog import iter_tenant_feature_files, load_labels
    from app.modules.dataset.samples import SAMPLE_FIELDS
    from app.modules.export.portable_export import write_feature_bundle
    from app.storage.metadata_db import _execute, _fetch_all
    from app.modules.saas.tenant_context import system_scope

    with system_scope("personal export: read a request"):
        rows = _fetch_all(
            "SELECT * FROM personal_exports WHERE export_id = %s", (str(export_id),))
    if not rows:
        raise PersonalExportError("không tìm thấy yêu cầu xuất", status_code=404)
    job = dict(rows[0])
    tenant = job["tenant_id"]
    user_id = str(job["user_id"])

    with system_scope("personal export: mark running"):
        _execute(
            "UPDATE personal_exports SET status = 'running' WHERE export_id = %s",
            (str(export_id),))

    target = _export_root() / f"{tenant}_{user_id}_{export_id}.zip"
    partial = target.with_suffix(".zip.part")

    try:
        owned = _owned_rows(tenant, user_id)

        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as bundle:
            added = write_feature_bundle(bundle, owned, iter_tenant_feature_files(tenant),
                                         Path(settings.dataset_root), SAMPLE_FIELDS,
                                         labels=load_labels(tenant))
            bundle.writestr("README.txt", _readme(tenant, len(owned), added))

        from app.modules.saas.tenant_lifecycle import finish_partial

        finish_partial(partial, target)
        size = target.stat().st_size
        with system_scope("personal export: mark ready"):
            _execute(
                "UPDATE personal_exports SET status = 'ready', file_path = %s, "
                "size_bytes = %s, sample_count = %s, completed_at = NOW() "
                "WHERE export_id = %s",
                (str(target), size, len(owned), str(export_id)),
            )
        logger.info("[PERSONAL_EXPORT] %s xong: %s (%d mau, %d byte)",
                    user_id, target.name, len(owned), size)
        return {"export_id": export_id, "status": "ready", "size_bytes": size,
                "sample_count": len(owned)}

    except Exception as exc:
        from app.modules.saas.tenant_lifecycle import discard_partial

        discard_partial(partial)
        with system_scope("personal export: mark failed"):
            _execute(
                "UPDATE personal_exports SET status = 'failed', error = %s, "
                "completed_at = NOW() WHERE export_id = %s",
                (f"{type(exc).__name__}: {exc}"[:500], str(export_id)),
            )
        logger.error("[PERSONAL_EXPORT] %s hỏng: %s", user_id, exc)
        raise


def list_exports(tenant_id: str, user_id: str) -> List[Dict[str, Any]]:
    """Gọi từ router, dưới phạm vi tenant của chính request — không cần
    `system_scope`, cùng lý do đã ghi ở `request_export`."""
    from app.storage.metadata_db import _fetch_all
    from app.modules.saas.tenancy import normalize_tenant_id

    tenant = normalize_tenant_id(tenant_id)
    rows = _fetch_all(
        "SELECT export_id, status, size_bytes, sample_count, error, "
        "created_at, completed_at, expires_at FROM personal_exports "
        "WHERE tenant_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT 30",
        (tenant, str(user_id)),
    )
    return [dict(r) for r in rows]


def export_file(tenant_id: str, user_id: str, export_id: str) -> Path:
    """Đường dẫn tệp của một bản xuất, sau khi kiểm nó là CỦA ĐÚNG NGƯỜI này.

    Phạm vi theo cả tenant, user_id lẫn export_id — một UUID đoán trúng không
    được phép trở thành đường tải dữ liệu của người khác. Không cần
    `system_scope`, cùng lý do đã ghi ở `request_export`.
    """
    from app.storage.metadata_db import _fetch_all
    from app.modules.saas.tenancy import normalize_tenant_id

    tenant = normalize_tenant_id(tenant_id)
    rows = _fetch_all(
        "SELECT status, file_path FROM personal_exports "
        "WHERE tenant_id = %s AND user_id = %s AND export_id = %s",
        (tenant, str(user_id), str(export_id)),
    )
    if not rows:
        raise PersonalExportError("không tìm thấy bản xuất", status_code=404)
    row = rows[0]
    if row["status"] != "ready" or not row["file_path"]:
        raise PersonalExportError("bản xuất chưa sẵn sàng", status_code=409)
    path = Path(row["file_path"])
    if not path.exists():
        raise PersonalExportError("tệp không còn trên máy chủ — có thể đã hết hạn",
                                  status_code=410)
    return path


def cleanup_expired_exports() -> int:
    """Xoá tệp của những bản xuất cá nhân đã hết hạn. Cùng khuôn với
    `tenant_lifecycle.cleanup_expired_exports`."""
    from app.storage.metadata_db import _execute, _fetch_all
    from app.modules.saas.tenant_context import system_scope

    with system_scope("personal export: find expired"):
        rows = _fetch_all(
            "SELECT export_id, file_path FROM personal_exports "
            "WHERE status = 'ready' AND expires_at <= NOW()"
        )
    removed = 0
    for row in rows:
        path = Path(row["file_path"] or "")
        try:
            if path.exists():
                path.unlink()
            removed += 1
        except OSError as exc:
            logger.warning("[PERSONAL_EXPORT] không xoá được %s: %s", path, exc)
            continue
        with system_scope("personal export: mark expired"):
            _execute(
                "UPDATE personal_exports SET status = 'expired', file_path = NULL "
                "WHERE export_id = %s",
                (str(row["export_id"]),),
            )
    if removed:
        logger.info("[PERSONAL_EXPORT] dọn %d bản xuất cá nhân hết hạn", removed)
    return removed
