from typing import Optional, Dict, Any
import json
import unicodedata
from pathlib import Path
from filelock import FileLock
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from app import audit
from app.rate_limit_deps import limit_catalog
from app.dataset_manager import (
    get_or_register_class,
    list_classes,
    normalize_dialect,
    normalize_region,
)
from app.processing.class_registry import AlphabetLabelError, is_alphabet_dialect
from app.dataset_samples import list_samples
from app.balancer import build_balance_plan
from app.api_validation import validate_label, validate_language, validate_dialect
from app.catalog_sync import (
    CatalogSyncError,
    sync_update_class,
    sync_soft_delete_class,
    sync_restore_class,
    sync_purge_class,
    list_trash_classes,
    bulk_restore_classes,
    bulk_purge_classes,
    empty_class_trash,
)
from app.config import settings
from app.auth import get_current_user, require_admin, require_tenant_editor
from app.tenant_context import require_tenant
from app.quota_deps import guard_quota, tenant_of
from app.webhooks import emit

router = APIRouter(prefix="/classes", tags=["classes"])

# ---------------------------------------------------------------------------
# Preferences file (replaces localStorage on frontend)
# ---------------------------------------------------------------------------
_PREFS_PATH = Path(settings.dataset_root) / "user_preferences.json"
_PREFS_LOCK = str(_PREFS_PATH) + ".lock"


def _load_prefs() -> dict:
    if not _PREFS_PATH.exists():
        return {}
    try:
        with open(_PREFS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_prefs(data: dict) -> None:
    # Callers MUST already hold the prefs FileLock (set_preference does). This
    # helper deliberately does NOT re-acquire it: FileLock is not reentrant
    # across instances in the same process, so a nested acquire self-deadlocks
    # (the request hangs forever, leaking a thread-pool worker + poisoning the
    # lock for every later preference write).
    _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Text normalization for prefix matching (remove diacritics)
# ---------------------------------------------------------------------------
def _normalize_search(text: str) -> str:
    """Normalize text for prefix search: lowercase, remove diacritics.

    Correct for word signs \u2014 typing "tom" should find "t\u00f4m". NOT correct for the
    fingerspelling alphabet, where \u0102/\u00c2/\u0110/\u00ca/\u00d4/\u01a0/\u01af are distinct letters; use
    _normalize_alphabet_search there instead.
    """
    if not text:
        return ""
    t = text.strip().lower()
    t = t.replace("\u0111", "d").replace("\u0110", "D")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t


def _normalize_alphabet_search(text: str) -> str:
    """Diacritic-PRESERVING normalization for fingerspelling labels.

    Suggesting "A" to someone who typed "\u00c2" walks them into recording the wrong
    class, which is the same letter collision the slug fix removed \u2014 this time
    committed by the recorder rather than the code. Case and Unicode form are
    still normalized so "\u00e2" and a decomposed "\u00c2" match the same entry.
    """
    return unicodedata.normalize("NFC", (text or "").strip()).lower()


@router.post("/register", dependencies=[Depends(limit_catalog)])
def register_class(
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(require_tenant_editor),
):
    """Thêm một lớp từ vựng vào danh mục của tổ chức.

    Cổng quyền là `require_tenant_editor`, không phải `get_current_user`: đây
    là ghi vào danh mục dùng chung của cả tổ chức, không phải dữ liệu riêng
    của người gọi. Xem chú thích ở chính dependency đó về lỗ hổng nó bịt.
    """
    guard_quota(current_user, "classes")
    label = validate_label(payload.get("label"))
    language = validate_language(payload.get("language", "vn"))
    dialect = validate_dialect(normalize_dialect(payload.get("dialect", "")))
    is_common_global = bool(payload.get("is_common_global", False))
    is_common_language = bool(payload.get("is_common_language", False))
    # Vùng của KÝ HIỆU, trục riêng với `dialect`. Bỏ trống thì `unclassified`,
    # và đó là trạng thái có nghĩa chứ không phải chỗ trống — xem
    # `REGION_UNCLASSIFIED`. Nhận ở đây là điều kiện để hai biến thể miền của
    # cùng một từ tạo được qua giao diện; thiếu nó thì mọi lớp mới sinh ra đều
    # `unclassified` và lớp thứ hai đụng khoá duy nhất.
    region = normalize_region(payload.get("region"))
    try:
        meta = get_or_register_class(
            label_original=label,
            language=language,
            dialect=dialect,
            is_common_global=is_common_global,
            is_common_language=is_common_language,
            region=region,
        )
    except AlphabetLabelError as exc:
        # A typo in a fingerspelling label, surfaced to the recorder rather than
        # accepted as a new class that would collide with a real letter.
        raise HTTPException(status_code=422, detail=str(exc))

    emit(
        tenant_of(current_user), "class.created",
        {
            "class_uid": meta.class_uid, "slug": meta.slug,
            "label": meta.label_original, "language": meta.language,
            "dialect": meta.dialect, "region": meta.region,
        },
    )
    return {
        "success": True,
        "class_uid": meta.class_uid,
        "slug": meta.slug,
        "language": meta.language,
        "dialect": meta.dialect,
        "region": meta.region,
    }


@router.get("/list")
def list_endpoint(language: Optional[str] = None, dialect: Optional[str] = None):
    # `count` cũng phải theo phạm vi. Lọc `items` mà để `count` toàn cục thì
    # giao diện không thấy lớp của tenant khác nhưng vẫn BIẾT chúng tồn tại —
    # rò siêu dữ liệu mà không rò một hàng nào.
    metas = list_classes(language=language, dialect=dialect,
                         tenant_id=require_tenant())
    return {"count": len(metas), "items": [m.to_label_row() for m in metas]}


@router.get("/suggest")
def suggest_labels(
    q: str = Query("", description="Search prefix"),
    language: Optional[str] = None,
    dialect: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
):
    """Autocomplete label suggestions by prefix match.

    Returns labels from the currently selected language+dialect that
    start with the query text (diacritics-insensitive prefix match).
    When q is empty, returns the first `limit` labels sorted A-Z.
    """
    metas = list_classes(language=language, dialect=dialect,
                         tenant_id=require_tenant())

    # Deduplicate by label_original
    seen: set = set()
    unique_labels: list = []
    for m in metas:
        label = m.label_original.strip()
        if label and label not in seen:
            seen.add(label)
            unique_labels.append(label)

    unique_labels.sort()

    # The fingerspelling alphabet is a closed set of distinct letters, so its
    # search must not fold Â into A. Word signs keep the forgiving match.
    normalize = (
        _normalize_alphabet_search if is_alphabet_dialect(dialect or "") else _normalize_search
    )
    query_norm = normalize(q)

    if not query_norm:
        return {"suggestions": unique_labels[:limit]}

    matches = [
        label for label in unique_labels if normalize(label).startswith(query_norm)
    ]
    return {"suggestions": matches[:limit]}


@router.get("/collectors")
def search_collectors(
    q: str = Query("", description="Search prefix for collector name"),
    language: Optional[str] = None,
    dialect: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
):
    """Search unique collectors (user_ids) from sample data.

    Optionally filtered by language and dialect.
    Returns collector names matching the query prefix.
    """
    # Đây là chỗ rò nặng nhất trong tệp: không phải rò một hàng dữ liệu, mà rò
    # DANH SÁCH NGƯỜI của tenant khác. Một lượt đọc toàn cục ở đây biến ô tìm
    # kiếm thành danh bạ xuyên tổ chức.
    samples = list_samples(require_tenant())

    seen: set = set()
    collectors: list = []
    for s in samples:
        user_id = (s.get("user_id") or "").strip()
        if not user_id or user_id in seen:
            continue
        if language and s.get("language", "") != language:
            continue
        if dialect and s.get("dialect", "") != dialect:
            continue
        seen.add(user_id)
        collectors.append(user_id)

    collectors.sort()

    query_norm = _normalize_search(q)
    if not query_norm:
        return {"collectors": collectors[:limit]}

    matches = [
        name for name in collectors if _normalize_search(name).startswith(query_norm)
    ]
    return {"collectors": matches[:limit]}


def _prefs_bucket(current_user: Dict[str, Any]) -> str:
    """Khoá ngăn riêng của một tài khoản trong tệp tuỳ chọn dùng chung.

    Tệp mang tên `user_preferences.json` nhưng tới trước v4 nó KHÔNG theo người
    dùng: mọi khoá nằm chung ở mức trên cùng, nên ngôn ngữ và phương ngữ vừa
    chọn của một người ghi đè lên của tất cả những người còn lại — kể cả người
    ở tenant khác. Không phải rò rỉ dữ liệu nhạy cảm, nhưng là trạng thái dùng
    chung xuyên biên giới tenant, đúng thứ mà phần còn lại của hệ thống bỏ
    công ngăn.

    Ngăn theo tenant lẫn tài khoản: chỉ theo tài khoản là đủ để cô lập, nhưng
    có tenant trong khoá khiến việc xoá sạch một tenant lúc purge thành một
    phép lọc tiền tố thay vì phải dò từng id người dùng.
    """
    from app.tenancy import normalize_tenant_id

    tho = (current_user.get("tenant_id") or "").strip()
    if not tho:
        # Khoá tuỳ chọn mang tenant làm tiền tố để purge một tenant thành phép
        # lọc tiền tố. Rơi về `default` khi thiếu sẽ nhét tuỳ chọn của người
        # dùng vào không gian khoá của tenant khởi tạo — và lượt purge tenant
        # đó sẽ xoá nhầm.
        raise HTTPException(status_code=400,
                            detail="Không xác định được tenant của tài khoản")
    tenant = normalize_tenant_id(tho)
    return f"{tenant}::{current_user.get('id')}"


@router.get("/preferences")
def get_preference(
    key: str = Query(..., description="Preference key"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get a user preference value by key."""
    prefs = _load_prefs()
    mine = prefs.get(_prefs_bucket(current_user)) or {}
    if key in mine:
        return {"key": key, "value": mine[key]}
    # Rơi về giá trị cũ ở mức trên cùng, MỘT LẦN: những khoá đó do bản trước
    # v4 ghi và là tuỳ chọn thật của ai đó. Đọc được nhưng không ghi vào nữa,
    # nên chúng tắt dần khi mỗi người lưu lại lựa chọn của mình.
    legacy = prefs.get(key)
    return {"key": key, "value": legacy if not isinstance(legacy, dict) else None}


@router.post("/preferences")
def set_preference(
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Set a user preference key-value pair."""
    key = payload.get("key", "").strip()
    value = payload.get("value")
    if not key:
        raise HTTPException(status_code=400, detail="Key is required")

    bucket = _prefs_bucket(current_user)
    lock = FileLock(_PREFS_LOCK)
    with lock:
        prefs = _load_prefs()
        mine = prefs.get(bucket)
        # Một khoá cũ ở mức trên cùng có thể trùng tên với một ngăn; kiểm kiểu
        # ở đây để dữ liệu cũ không biến thành ngăn của ai đó.
        if not isinstance(mine, dict):
            mine = {}
        mine[key] = value
        prefs[bucket] = mine
        _save_prefs(prefs)

    return {"success": True, "key": key, "value": value}


@router.get("/stats")
def stats(language: Optional[str] = None, dialect: Optional[str] = None):
    scope = require_tenant()
    metas = list_classes(language=language, dialect=dialect, tenant_id=scope)
    samples = list_samples(scope)
    counts = {m.class_uid: 0 for m in metas}
    for s in samples:
        cid = s.get("class_uid")
        if cid in counts:
            counts[cid] += 1
    max_count = max(counts.values(), default=0)
    distribution = []
    for m in metas:
        c = counts[m.class_uid]
        distribution.append(
            {
                "class_uid": m.class_uid,
                "slug": m.slug,
                "label_original": m.label_original,
                "language": m.language,
                "dialect": m.dialect,
                "count": c,
                "imbalance_ratio": round((c / max_count) if max_count else 0.0, 4),
            }
        )
    return {
        "total_classes": len(metas),
        "max_count": max_count,
        "distribution": distribution,
    }


@router.get("/community-stats")
def community_stats():
    """Lightweight aggregate for the public dashboard's "Cộng đồng" block.

    Returns just the four scalars the UI shows so the client no longer has to
    download the full class list (~14KB) + every session and reduce them in the
    browser. Aggregation happens server-side; response is ~120 bytes.
    """
    # QUYẾT ĐỊNH CÒN MỞ — đọc hết khối này trước khi sửa. Xem
    # docs/01-architecture/COMMUNITY_DATA_COMMONS.md §0 và §10.
    #
    # Endpoint này KHÔNG đọc mặt phẳng Community. Nó đọc
    # `settings.public_tenant_id`, mặc định là `"default"` — và `default` là một
    # tenant TỔ CHỨC bình thường (`tenant_type='ORGANIZATION'`,
    # `is_system_reserved=FALSE`) đang giữ corpus nghiên cứu thật. Commons thật
    # là một tenant KHÁC: `tenant_id='community'`, `tenant_type='COMMUNITY'`.
    #
    # Nói cách khác, cái tên `community-stats` đang lặp lại đúng sai lầm mà §0
    # của tài liệu ấy đã sửa một lần: gọi mặt phẳng hệ thống/khởi tạo là
    # "Community". Community Data Commons hiện là **0 dòng mã**, nên hiện chưa
    # có số liệu cộng đồng nào để hiển thị.
    #
    # Và theo §10, Community KHÔNG phải một mặt phẳng ngoại lệ: nó là một tenant
    # dự trữ, chịu ĐÚNG RLS/RBAC/cách ly như mọi tenant khác, với quy tắc "tư
    # cách thành viên không bao giờ là điều kiện đủ — mọi phép kiểm phải hỏi một
    # QUYỀN cụ thể". Nên đừng hợp thức hoá endpoint này bằng câu "cộng đồng thì
    # công khai"; nó cần một lý do gắn với quyền.
    #
    # Hành vi hiện tại được GIỮ NGUYÊN có chủ ý (vẫn là tenant khởi tạo, giống
    # trước khi có tenant), vì đổi nó là một quyết định chính sách chứ không
    # phải một bản vá cách ly. Ba lựa chọn, chưa chọn:
    #   (a) đọc tenant `community` -> hiện trả 0, trung thực với trạng thái thật
    #   (b) đổi tên endpoint thành `/classes/public-corpus-stats` và ghi rõ nó
    #       công bố corpus của tenant khởi tạo
    #   (c) gắn một quyền tường minh thay vì để nó mở cho mọi người gọi
    #
    # Điều đã sửa được ngay: phạm vi là TƯỜNG MINH và không phải "cộng mọi
    # tenant lại". Bản trước đọc toàn bộ kho, nên bốn con số này rò quy mô của
    # mọi tổ chức. Nay thêm dữ liệu vào một tenant riêng KHÔNG làm chúng đổi —
    # đó là bất biến READ-3 đã đo được.
    cong_bo = (settings.public_tenant_id or "").strip()
    if not cong_bo:
        # Không cấu hình thì không công bố gì. Trả 0 chứ không rơi về phạm vi
        # người gọi và cũng không rơi về toàn bộ kho.
        return {"labels_count": 0, "total_samples": 0,
                "contributors_count": 0, "regions_count": 0}
    metas = list_classes(tenant_id=cong_bo)
    samples = list_samples(cong_bo)

    contributors = {
        (s.get("user_id") or "").strip() for s in samples
    }
    contributors.discard("")

    regions = {
        (getattr(m, "dialect", "") or "").strip() for m in metas
    }
    regions.discard("")

    return {
        "labels_count": len(metas),
        "total_samples": len(samples),
        "contributors_count": len(contributors),
        "regions_count": len(regions),
    }


@router.get("/balance")
def balance_plan(target: int | None = None):
    plan = build_balance_plan(require_tenant(), target=target)
    return plan


@router.put("/{class_ref}", dependencies=[Depends(limit_catalog)])
def update_class(
    class_ref: str,
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(require_admin),
):
    try:
        result = sync_update_class(class_ref, payload, tenant_id=require_tenant())
        return {
            "success": True,
            "message": f"Nh\u00e3n \u0111\u01b0\u1ee3c c\u1eadp nh\u1eadt th\u00e0nh c\u00f4ng: {result.get('slug', '')}",
            "op_id": result.get("op_id"),
            "operation_logs": result.get("operation_logs"),
            **result,
        }
    except CatalogSyncError as exc:
        return {
            "success": False,
            "message": f"L\u1ed7i c\u1eadp nh\u1eadt nh\u00e3n: {str(exc)}",
            "error_code": exc.error_code,
            "operation_logs": getattr(exc, "logs", None),
        }


@router.get("/trash")
def list_class_trash(current_user: Dict[str, Any] = Depends(require_admin)):
    """List soft-deleted classes (Trash). Admin only."""
    try:
        items = list_trash_classes()
        return {"count": len(items), "items": items}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Kh\u00f4ng \u0111\u1ecdc \u0111\u01b0\u1ee3c th\u00f9ng r\u00e1c: {exc}")


@router.post("/trash/restore", dependencies=[Depends(limit_catalog)])
def bulk_restore_classes_endpoint(
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(require_admin),
):
    """Restore several soft-deleted classes at once. Body: {class_uids: [...]}."""
    uids = payload.get("class_uids") or []
    result = bulk_restore_classes(uids)
    return {"success": True, "message": f"\u0110\u00e3 kh\u00f4i ph\u1ee5c {result['ok_count']} nh\u00e3n.", **result}


@router.post("/trash/purge", dependencies=[Depends(limit_catalog)])
def bulk_purge_classes_endpoint(
    request: Request,
    payload: dict = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_admin),
):
    """Permanently delete classes. Body: {class_uids: [...]} for a selection, or
    {all: true} to empty the whole class trash. Irreversible."""
    if payload.get("all"):
        result = empty_class_trash()
    else:
        result = bulk_purge_classes(payload.get("class_uids") or [])
    audit.record("data.class.purge.bulk", actor=current_user, request=request,
                 target_type="class", detail={
                     "all": bool(payload.get("all")),
                     "requested": payload.get("class_uids") or [],
                     "ok_count": result.get("ok_count"),
                 })
    return {"success": True, "message": f"\u0110\u00e3 x\u00f3a v\u0129nh vi\u1ec5n {result['ok_count']} nh\u00e3n.", **result}


@router.delete("/{class_ref}", dependencies=[Depends(limit_catalog)])
def delete_class(
    class_ref: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin),
):
    """Soft-delete a class to Trash (restorable). Files/Drive are kept until purge."""
    try:
        result = sync_soft_delete_class(class_ref, tenant_id=require_tenant())
        audit.record("data.class.soft_delete", actor=current_user, request=request,
                     target_type="class", target_id=result.get("class_uid") or class_ref,
                     detail={"sample_count": result.get("sample_count")})
        return {
            "success": True,
            "message": f"\u0110\u00e3 chuy\u1ec3n nh\u00e3n v\u00e0o th\u00f9ng r\u00e1c ({result.get('sample_count', 0)} m\u1eabu). C\u00f3 th\u1ec3 kh\u00f4i ph\u1ee5c.",
            "op_id": result.get("op_id"),
            "operation_logs": result.get("operation_logs"),
            **result,
        }
    except CatalogSyncError as exc:
        return {
            "success": False,
            "message": f"L\u1ed7i x\u00f3a nh\u00e3n: {str(exc)}",
            "error_code": exc.error_code,
            "operation_logs": getattr(exc, "logs", None),
        }


@router.post("/{class_uid}/restore", dependencies=[Depends(limit_catalog)])
def restore_class_endpoint(
    class_uid: str,
    current_user: Dict[str, Any] = Depends(require_admin),
):
    """Restore a soft-deleted class from Trash."""
    try:
        result = sync_restore_class(class_uid, tenant_id=require_tenant())
        return {"success": True, "message": "\u0110\u00e3 kh\u00f4i ph\u1ee5c nh\u00e3n t\u1eeb th\u00f9ng r\u00e1c.", **result}
    except CatalogSyncError as exc:
        return {"success": False, "message": f"L\u1ed7i kh\u00f4i ph\u1ee5c nh\u00e3n: {str(exc)}", "error_code": exc.error_code}


@router.delete("/{class_uid}/purge", dependencies=[Depends(limit_catalog)])
def purge_class_endpoint(
    class_uid: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin),
):
    """Permanently delete a class (files + Drive + DB). Irreversible.

    Ghi một dòng kiểm toán BỀN. Đây là hành động không hồi được duy nhất ở mặt
    phẳng dữ liệu, và cho tới bản này nó không để lại dấu vết nào ngoài
    `operation_logs` phù du: lần purge `lop-thu-70eb62` ngày 2026-08-08 không
    có dòng nào trong `audit_log` để tra lại ai đã làm và lúc nào.
    """
    try:
        result = sync_purge_class(class_uid, tenant_id=require_tenant())
        audit.record("data.class.purge", actor=current_user, request=request,
                     target_type="class", target_id=class_uid,
                     detail={"op_id": result.get("op_id")})
        return {"success": True, "message": "\u0110\u00e3 x\u00f3a v\u0129nh vi\u1ec5n nh\u00e3n.", **result}
    except CatalogSyncError as exc:
        return {"success": False, "message": f"L\u1ed7i x\u00f3a v\u0129nh vi\u1ec5n: {str(exc)}", "error_code": exc.error_code}
