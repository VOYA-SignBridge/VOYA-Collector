"""Học ký hiệu — API CÔNG KHAI cho trang `/learn`.

Đối tượng: học sinh khiếm thính, giáo viên, phụ huynh — thường KHÔNG có tài
khoản. Nên hai đường này nằm trong `PUBLIC_ROUTES` của `access_gate` và không
đòi đăng nhập, y như trang đọc điều khoản.

Hai đường dùng QUERY STRING thay vì tham số đường dẫn (`/sign?slug=xin-chao`
chứ không phải `/sign/xin-chao`): cổng công khai khớp đường NGUYÊN VĂN, cố ý,
và một mẫu đường động sẽ phải mở cả một tiền tố.

Dữ liệu "đã có mẫu trong hệ thống" đọc từ tenant CÔNG BỐ
(`settings.public_tenant_id`) — cùng phạm vi với `/classes/community-stats`,
và cùng lý do: một đường công khai không được cộng dồn mọi tổ chức.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app import learn_catalog
from app.config import settings

router = APIRouter(prefix="/learn", tags=["learn"])

#: Nguồn ghi ở cuối mọi phản hồi, để giao diện hiện đúng câu.
_ATTRIBUTION = (
    "Từ vựng và định nghĩa: Danh mục Ngôn ngữ ký hiệu tiếng Việt — dự án QIPEDC, "
    "Bộ Giáo dục và Đào tạo (qipedc.moet.gov.vn). Video mẫu phát trực tiếp từ máy chủ "
    "của dự án, bản quyền thuộc về QIPEDC/Bộ GD&ĐT."
)


def _own_classes_by_slug() -> Dict[str, List[Dict[str, Any]]]:
    """Lớp của tenant công bố, gộp theo `slug`, kèm số mẫu ĐÃ DUYỆT."""
    tenant = (settings.public_tenant_id or "").strip()
    if not tenant:
        return {}
    from app import moderation
    from app.dataset_manager import list_classes
    from app.dataset_samples import list_samples

    samples = moderation.filter_rows(list_samples(tenant), viewer_id=None).kept
    per_class: Dict[str, int] = {}
    for s in samples:
        uid = (s.get("class_uid") or "").strip()
        if uid:
            per_class[uid] = per_class.get(uid, 0) + 1

    # `list_classes` trả `ClassMetadata` (dataclass), không phải dict — lớp đã
    # xoá mềm không có mặt trong danh sách này.
    out: Dict[str, List[Dict[str, Any]]] = {}
    for c in list_classes(tenant_id=tenant):
        slug = (getattr(c, "slug", "") or "").strip()
        if not slug:
            continue
        uid = str(getattr(c, "class_uid", "") or "")
        out.setdefault(slug, []).append({
            "class_uid": uid,
            "label": getattr(c, "label_original", "") or slug,
            "region": getattr(c, "region", "") or "",
            "dialect": getattr(c, "dialect", "") or "",
            "sample_count": per_class.get(uid, 0),
        })
    return out


def _attach_own(word: Dict[str, Any], own: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    mine = own.get(word["slug"], [])
    return {**word, "own": mine, "own_sample_count": sum(m["sample_count"] for m in mine)}


@router.get("/signs")
def list_signs(
    q: str = Query("", max_length=100, description="Từ cần tìm; không dấu cũng được."),
    region: str = Query("", max_length=16),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    if region and region not in learn_catalog.REGION_NAME:
        raise HTTPException(status_code=422, detail={"code": "bad_region",
                                                     "message": "Vùng phải là bac, trung, nam hoặc khong_ghi."})
    words = learn_catalog.search(q, region, limit)
    own = _own_classes_by_slug() if words else {}
    return {
        "items": [_attach_own(w, own) for w in words],
        "total_words": learn_catalog.count()["words"],
        "attribution": _ATTRIBUTION,
        "dictionary_url": learn_catalog.QIPEDC_DICTIONARY_URL,
    }


@router.get("/sign")
def get_sign(slug: str = Query(..., min_length=1, max_length=120)) -> Dict[str, Any]:
    word: Optional[Dict[str, Any]] = learn_catalog.get(slug)
    if word is None:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "Không có ký hiệu này trong danh mục."})
    return {
        **_attach_own(word, _own_classes_by_slug()),
        "attribution": _ATTRIBUTION,
        "dictionary_url": learn_catalog.QIPEDC_DICTIONARY_URL,
    }
