"""Lookup list: các Google Sheet tra cứu của từng tổ chức trên Drive.

Thiết kế: docs/02-data/DRIVE_STORAGE_AND_LOOKUP_LIST.md (mục 2-5). Tên thư mục,
tên tệp, tên tab lấy từ `app.storage.drive_layout` — không gõ lại ở đây.

    <gốc Drive>/Lookup list/platform - Tenants, platform - Storage layout
    Community/Lookup list/community - Labels … community - Audit logs
    Tenants/<slug>/Lookup list/<slug> - Labels … <slug> - Audit logs

Database là nguồn sự thật; Sheet chỉ để người đọc tra cứu (sửa tay không chảy
ngược). Ba quy tắc để không tốn tài nguyên:

1. **Chỉ làm khi có đổi.** Mỗi Sheet có một dấu vân tay tính NGAY TRONG DB (một
   câu `md5(string_agg(...))`). Trùng lần trước thì dừng: không dựng dòng, không
   gọi Drive.
2. **Đợi dữ liệu lắng.** Có thay đổi trong `LOOKUP_LIST_SETTLE_SECONDS` vừa qua
   (một đợt tách video đang ghi dở) thì để lượt sau.
3. **Chỉ ghi dòng đã đổi.** So với bản đã ghi lần trước (lưu cạnh dataset): dòng
   đổi thì ghi đè đúng dòng đó, dòng mới thì nối xuống cuối. Chỉ viết lại cả bảng
   khi đổi tiêu đề, bớt dòng, hoặc đổi quá nhiều dòng một lúc.

`Models` và `Audit logs` đổi hiếm, nên chỉ xét mỗi ngày một lần vào giờ thấp
điểm (`LOOKUP_LIST_DAILY_HOUR`), trừ lần dựng đầu tiên.

Hàm vào là `sync_all()`, do task toàn nền tảng `export_tasks.sync_lookup_lists`
gọi (phạm vi hệ thống do worker đặt). Chạy tay thì bọc `system_scope`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.config import settings
from app.storage import drive_layout as dl

logger = logging.getLogger(__name__)

SHEET_MIME = "application/vnd.google-apps.spreadsheet"
FOLDER_URL = "https://drive.google.com/drive/folders/{}"
#: Thời gian dữ liệu phải đứng yên trước khi đẩy lên Sheet.
SETTLE_SECONDS = int(os.getenv("LOOKUP_LIST_SETTLE_SECONDS", "120"))
#: Giờ (theo `LOOKUP_LIST_TZ`) xét các Sheet đổi hiếm: Models, Audit logs, platform.
DAILY_HOUR = int(os.getenv("LOOKUP_LIST_DAILY_HOUR", "2"))
DAILY_TZ = os.getenv("LOOKUP_LIST_TZ", "Asia/Ho_Chi_Minh")
#: Quá số dòng đổi này thì viết lại cả bảng (một lượt gọi) thay vì từng dòng.
FULL_REWRITE_ROWS = int(os.getenv("LOOKUP_LIST_FULL_REWRITE_ROWS", "200"))
#: Phiên bản bố cục ghi vào `platform - Storage layout`.
LAYOUT_VERSION = ("tenant-v1", "2026-10-18")

#: action trong `audit_log` -> `log_category`. Không khớp tiền tố nào thì KHÔNG
#: đưa lên Sheet (vẫn ở DB). `security` có tên ở đây nhưng bị loại khỏi Sheet.
AUDIT_CATEGORIES: Tuple[Tuple[str, str], ...] = (
    ("data.class.", "label"), ("vocabulary.", "label"), ("label.", "label"),
    ("data.sample.", "sample"), ("moderation.", "sample"), ("samples.", "sample"),
    ("collection_session.", "sample"),
    ("video.", "video"), ("raw_upload.", "video"),
    ("dataset_version.", "dataset"),
    ("model.", "model"), ("training.", "model"),
    ("member.", "member"), ("tenant.member", "member"), ("tenant.invitation", "member"),
    ("account.", "member"), ("authz.", "member"), ("tenant.home_assigned", "member"),
    ("tenant.data_moved", "storage"), ("storage.", "storage"), ("personal_export.", "storage"),
    ("tenant.", "tenant"),
    ("security.", "security"), ("api_key.", "security"), ("auth.", "security"),
)
AUDIT_SKIPPED_ACTIONS = ("tenant.active.switched",)
AUDIT_SHEET_EXCLUDED_CATEGORIES = ("security",)


# ------------------------------------------------------------------ trạng thái


def _state_dir() -> Path:
    return Path(settings.dataset_root) / ".lookup_list"


def _state_path(prefix: str, sheet_type: str) -> Path:
    safe = re.sub(r"[^a-z0-9]+", "-", f"{prefix}-{sheet_type}".lower()).strip("-")
    return _state_dir() / f"{safe}.json"


def _load_state(prefix: str, sheet_type: str) -> Dict[str, Any]:
    try:
        return json.loads(_state_path(prefix, sheet_type).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(prefix: str, sheet_type: str, state: Dict[str, Any]) -> None:
    path = _state_path(prefix, sheet_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _cell(value: Any) -> str:
    """Cùng dạng chuỗi với CSV cũ: bool -> 0/1, thời gian -> ISO, None -> rỗng."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _row(record: Dict[str, Any], header: List[str]) -> List[str]:
    return [_cell(record.get(col)) for col in header]


# ------------------------------------------------------------------ Drive / Sheets


def _client():
    from app.storage.gdrive_client import get_gdrive_client

    return get_gdrive_client()


def ensure_tenant_skeleton(tenant_id: str) -> str:
    """Khung thư mục của một tổ chức; trả ID thư mục `Lookup list/` của nó."""
    client = _client()
    root = dl.tenant_drive_root(tenant_id)
    for tree in (dl.FEATURES_TREE, dl.RAW_VIDEOS_TREE, dl.MODELS_TREE):
        client.resolve_folder_path(f"{root}/{dl.DRIVE_TREE_NAMES[tree]}", create_missing=True)
    return client.resolve_folder_path(f"{root}/{dl.LOOKUP_LIST_DIRNAME}", create_missing=True)


def _ensure_sheet(folder_id: str, title: str, tab: str, state: Dict[str, Any]) -> Tuple[str, int, bool]:
    """(spreadsheet_id, gid, vừa_tạo). Tìm theo đúng tên trong thư mục, chưa có thì tạo."""
    from app.storage.gdrive_client import _drive_query_literal

    client = _client()
    cached = state.get("sheet") or {}
    files = client.service.files().list(
        q=(f"'{folder_id}' in parents and mimeType='{SHEET_MIME}' and trashed=false "
           f"and name='{_drive_query_literal(title)}'"),
        orderBy="createdTime", fields="files(id,name)",
    ).execute(num_retries=client.num_retries).get("files", [])
    files = [f for f in files if f.get("name") == title]
    if files:
        sid = files[0]["id"]
        if cached.get("id") == sid and "gid" in cached:
            return sid, int(cached["gid"]), False
        created = False
    else:
        sid = client.service.files().create(
            body={"name": title, "mimeType": SHEET_MIME, "parents": [folder_id]}, fields="id",
        ).execute(num_retries=client.num_retries)["id"]
        created = True
        logger.info("[LOOKUP] created sheet %s (%s)", title, sid)
    sheets = client.get_sheets_service()
    meta = sheets.spreadsheets().get(spreadsheetId=sid, fields="sheets(properties(sheetId,title))").execute(
        num_retries=client.num_retries)
    props = meta["sheets"][0]["properties"]
    gid = int(props["sheetId"])
    if created or props.get("title") != tab:
        sheets.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": [{
            "updateSheetProperties": {
                "properties": {"sheetId": gid, "title": tab, "gridProperties": {"frozenRowCount": 1}},
                "fields": "title,gridProperties.frozenRowCount",
            }}]}).execute(num_retries=client.num_retries)
    state["sheet"] = {"id": sid, "gid": gid}
    if created or cached.get("id") != sid:
        state.pop("matrix", None)  # bảng mới hoặc bảng khác: bản đã ghi không còn đúng
    return sid, gid, created


#: Bề rộng cố định (px) cho cột link — giãn theo nội dung thì một URL dài chiếm cả màn hình.
URL_COLUMN_PX = 220


def _fit_columns(sid: str, gid: int, header: List[str]) -> None:
    """Giãn cột theo nội dung để chữ không bị cắt; cột link giữ bề rộng cố định."""
    client = _client()
    reqs = []
    for i, col in enumerate(header):
        rng = {"sheetId": gid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1}
        if col == "storage_url":
            reqs.append({"updateDimensionProperties": {
                "range": rng, "properties": {"pixelSize": URL_COLUMN_PX}, "fields": "pixelSize"}})
        else:
            reqs.append({"autoResizeDimensions": {"dimensions": rng}})
    client.get_sheets_service().spreadsheets().batchUpdate(
        spreadsheetId=sid, body={"requests": reqs}).execute(num_retries=client.num_retries)


def _write(sid: str, gid: int, tab: str, header: List[str], rows: List[List[str]], state: Dict[str, Any]) -> str:
    """Ghi bảng, chỉ những dòng đã đổi so với lần trước. Trả về cách đã ghi."""
    client = _client()
    values = client.get_sheets_service().spreadsheets().values()
    width = len(header)
    matrix = [list(header)] + [(r + [""] * width)[:width] for r in rows]
    old = state.get("matrix")
    rng = f"'{tab}'"

    def _full() -> str:
        values.clear(spreadsheetId=sid, range=rng).execute(num_retries=client.num_retries)
        values.update(spreadsheetId=sid, range=f"{rng}!A1", valueInputOption="RAW",
                      body={"values": matrix}).execute(num_retries=client.num_retries)
        try:
            _fit_columns(sid, gid, header)
        except Exception as exc:  # chỉ là trình bày
            logger.warning("[LOOKUP] fit columns %s: %s", tab, exc)
        return f"viet lai {len(matrix) - 1} dong"

    if not old or old[0] != matrix[0] or len(matrix) < len(old):
        how = _full()
    else:
        changed = [i for i in range(1, len(old)) if old[i] != matrix[i]]
        new = matrix[len(old):]
        if len(changed) > FULL_REWRITE_ROWS:
            how = _full()
        elif not changed and not new:
            how = "khong doi"
        else:
            if changed:
                values.batchUpdate(spreadsheetId=sid, body={"valueInputOption": "RAW", "data": [
                    {"range": f"{rng}!A{i + 1}", "values": [matrix[i]]} for i in changed]}).execute(
                    num_retries=client.num_retries)
            if new:
                values.append(spreadsheetId=sid, range=f"{rng}!A1", valueInputOption="RAW",
                              insertDataOption="INSERT_ROWS", body={"values": new}).execute(
                    num_retries=client.num_retries)
            how = f"sua {len(changed)} dong, them {len(new)} dong"
    state["matrix"] = matrix
    return how


# ------------------------------------------------------------------ dữ liệu


def _db(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all

    return _fetch_all(sql, params)


def _fingerprint(table: str, key: str, tenant_id: str, ts_cols: Tuple[str, ...]) -> Tuple[str, Optional[datetime]]:
    """(md5 của mọi dòng của tổ chức, lần đổi gần nhất) — tính trong DB."""
    latest = ", ".join(f"max({c})" for c in ts_cols)
    row = _db(f"SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t.{key}), '')) AS fp, "
              f"greatest({latest}) AS last FROM {table} t WHERE t.tenant_id = %s", (tenant_id,))[0]
    return row["fp"], row["last"]


def _label_header() -> List[str]:
    from app.dataset_manager import LABEL_FIELDS
    from app.tenancy import TENANT_COLUMN

    return [c for c in LABEL_FIELDS if c != TENANT_COLUMN] + [
        "deleted_at", "sample_count", "approved_count", "pending_count", "updated_at", "storage_url"]


def _sample_header() -> List[str]:
    from app.dataset_samples import SAMPLE_FIELDS
    from app.tenancy import TENANT_COLUMN

    return [c for c in SAMPLE_FIELDS if c != TENANT_COLUMN] + ["deleted_at"]


def _video_header() -> List[str]:
    from app.raw_uploads import RAW_UPLOAD_FIELDS
    from app.tenancy import TENANT_COLUMN

    return [c for c in RAW_UPLOAD_FIELDS if c != TENANT_COLUMN] + [
        "deleted_at", "duration_sec", "size_bytes", "sample_count", "processing_status"]


DATASET_VERSION_HEADER = [
    "dataset_version", "created_at", "created_by", "sample_count", "class_count", "signer_count",
    "train_count", "val_count", "test_count", "split_method", "seed", "content_hash",
    "used_by_models", "note", "storage_url"]
MODEL_HEADER = [
    "model_name", "version", "status", "job_id", "model_type", "dataset_version", "test_acc", "test_f1",
    "class_count", "file_size_bytes", "sha256", "trained_at", "published_at", "published_by",
    "retired_at", "changelog", "notified_at", "storage_url"]
AUDIT_HEADER = [
    "event_id", "occurred_at", "log_category", "event_type", "actor", "object_type", "object_id",
    "object_name", "summary", "storage_url"]
TENANT_HEADER = [
    "tenant_id", "display_name", "tenant_type", "status", "created_at", "member_count", "label_count",
    "sample_count", "video_count", "storage_bytes", "published_models", "last_activity_at", "storage_url"]
LAYOUT_HEADER = ["folder", "contents", "written_by", "naming_rule", "storage_url",
                 "layout_version", "effective_from"]


def _labels(tenant_id: str, state: Dict[str, Any]) -> Tuple[List[str], List[List[str]]]:
    from app.dataset_manager import ClassMetadata, drive_class_folder

    header = _label_header()
    counts = {r["class_uid"]: r for r in _db(
        "SELECT class_uid, count(*) FILTER (WHERE deleted_at IS NULL) AS n, "
        "count(*) FILTER (WHERE deleted_at IS NULL AND review_status = 'approved') AS ok, "
        "count(*) FILTER (WHERE deleted_at IS NULL AND review_status = 'pending') AS wait, "
        "max(greatest(created_at, updated_at, deleted_at)) AS last "
        "FROM samples WHERE tenant_id = %s GROUP BY class_uid", (tenant_id,))}
    folders = state.setdefault("folders", {})
    client = _client()
    rows = []
    for c in _db("SELECT * FROM classes WHERE tenant_id = %s ORDER BY class_idx NULLS LAST, class_uid",
                 (tenant_id,)):
        cnt = counts.get(c["class_uid"]) or {}
        key = f"{c['class_uid']}|{c.get('folder_name')}|{c.get('dialect')}|{c.get('language')}"
        if not folders.get(key):
            try:
                meta = ClassMetadata(
                    class_uid=c["class_uid"], slug=c["slug"], label_original=c["label_original"],
                    language=c["language"], dialect=c["dialect"],
                    is_common_global=bool(c.get("is_common_global")),
                    is_common_language=bool(c.get("is_common_language")),
                    folder_override=c.get("folder_name") or None, tenant_id=tenant_id)
                fid = client.resolve_folder_path(drive_class_folder(meta), create_missing=False)
                folders[key] = FOLDER_URL.format(fid) if fid else ""
            except Exception as exc:
                logger.warning("[LOOKUP] class folder %s: %s", c["class_uid"], exc)
                folders[key] = ""
        rec = dict(c, sample_count=cnt.get("n", 0), approved_count=cnt.get("ok", 0),
                   pending_count=cnt.get("wait", 0),
                   updated_at=max([t for t in (c.get("created_at"), c.get("deleted_at"), cnt.get("last")) if t],
                                  default=None),
                   storage_url=folders[key])
        rows.append(_row(rec, header))
    return header, rows


def _samples(tenant_id: str, state: Dict[str, Any]) -> Tuple[List[str], List[List[str]]]:
    header = _sample_header()
    rows = [_row(r, header) for r in _db(
        "SELECT * FROM samples WHERE tenant_id = %s ORDER BY created_at NULLS FIRST, sample_uid", (tenant_id,))]
    return header, rows


def _videos(tenant_id: str, state: Dict[str, Any]) -> Tuple[List[str], List[List[str]]]:
    header = _video_header()
    per_session = {r["session_id"]: r["n"] for r in _db(
        "SELECT session_id, count(*) AS n FROM samples WHERE tenant_id = %s AND deleted_at IS NULL "
        "AND coalesce(session_id, '') <> '' GROUP BY session_id", (tenant_id,))}
    probes = state.setdefault("probes", {})
    rows = []
    for v in _db("SELECT * FROM raw_uploads WHERE tenant_id = %s ORDER BY created_at NULLS FIRST, upload_uid",
                 (tenant_id,)):
        probe = probes.get(v["upload_uid"])
        if probe is None:
            probe = probes[v["upload_uid"]] = _probe_video(v.get("local_path") or "")
        rec = dict(v, duration_sec=probe.get("duration_sec", ""), size_bytes=probe.get("size_bytes", ""),
                   sample_count=per_session.get(v.get("session_id") or "", 0),
                   processing_status=(v.get("status") or "").lower())
        rows.append(_row(rec, header))
    return header, rows


def _probe_video(local_path: str) -> Dict[str, Any]:
    """Thời lượng và dung lượng của tệp video trên đĩa (một lần mỗi video)."""
    out: Dict[str, Any] = {}
    path = Path(local_path)
    if not local_path or not path.is_file():
        return out
    out["size_bytes"] = path.stat().st_size
    try:
        import cv2

        cap = cv2.VideoCapture(str(path))
        fps, frames = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps and frames:
            out["duration_sec"] = round(frames / fps, 2)
    except Exception:
        pass
    return out


def _model_rows(tenant_id: str) -> List[Dict[str, Any]]:
    """Mỗi lần promote là một thư mục `Deploy <ngày>` có `deploy_manifest.json`."""
    client = _client()
    svc = client.service
    models_id = client.resolve_folder_path(
        f"{dl.tenant_drive_root(tenant_id)}/{dl.DRIVE_TREE_NAMES[dl.MODELS_TREE]}", create_missing=False)
    if not models_id:
        return []

    def ls(fid, q=""):
        return svc.files().list(q=f"'{fid}' in parents and trashed=false{q}", orderBy="createdTime",
                                fields="files(id,name,mimeType)", pageSize=1000).execute(
            num_retries=client.num_retries).get("files", [])

    out = []
    for model in ls(models_id, " and mimeType='application/vnd.google-apps.folder'"):
        deploys = []
        for d in ls(model["id"], " and mimeType='application/vnd.google-apps.folder'"):
            mf = next((f for f in ls(d["id"]) if f["name"] == "deploy_manifest.json"), None)
            manifest = {}
            if mf:
                try:
                    manifest = json.loads(svc.files().get_media(fileId=mf["id"]).execute().decode("utf-8"))
                except Exception as exc:
                    logger.warning("[LOOKUP] manifest %s/%s: %s", model["name"], d["name"], exc)
            deploys.append((manifest.get("promoted_at") or d["name"], d, manifest))
        deploys.sort(key=lambda x: x[0])
        for n, (published, d, m) in enumerate(deploys, start=1):
            ck = m.get("checkpoint") or {}
            metrics = m.get("metrics") or m.get("evaluation") or {}
            out.append({
                "model_name": m.get("model_id") or model["name"], "version": f"v{n}",
                "status": "published" if n == len(deploys) else "retired",
                "job_id": m.get("job_id"), "model_type": m.get("model_type"),
                "dataset_version": m.get("dataset_version"),
                "test_acc": metrics.get("test_acc"), "test_f1": metrics.get("test_f1"),
                "class_count": (m.get("output") or {}).get("num_classes"),
                "file_size_bytes": ck.get("size_bytes"), "sha256": ck.get("sha256"),
                "trained_at": m.get("trained_at"), "published_at": m.get("promoted_at"),
                "retired_at": deploys[n][2].get("promoted_at") if n < len(deploys) else None,
                "storage_url": FOLDER_URL.format(d["id"]),
            })
    return out


def _models(tenant_id: str, state: Dict[str, Any]) -> Tuple[List[str], List[List[str]]]:
    return MODEL_HEADER, [_row(r, MODEL_HEADER) for r in _model_rows(tenant_id)]


def audit_category(action: str) -> Optional[str]:
    if action in AUDIT_SKIPPED_ACTIONS:
        return None
    return next((cat for prefix, cat in AUDIT_CATEGORIES if action.startswith(prefix)), None)


def _audit(tenant_id: str, state: Dict[str, Any]) -> Tuple[List[str], List[List[str]]]:
    rows = []
    for a in _db("SELECT audit_id, created_at, action, actor_label, target_type, target_id, detail "
                 "FROM audit_log WHERE tenant_id = %s ORDER BY audit_id", (tenant_id,)):
        cat = audit_category(a["action"])
        if cat is None or cat in AUDIT_SHEET_EXCLUDED_CATEGORIES:
            continue
        detail = a.get("detail") or {}
        name = detail.get("name") or detail.get("label") or detail.get("slug") if isinstance(detail, dict) else ""
        summary = json.dumps(detail, ensure_ascii=False, default=str)[:300] if detail else ""
        rows.append(_row({"event_id": a["audit_id"], "occurred_at": a["created_at"], "log_category": cat,
                          "event_type": a["action"], "actor": a.get("actor_label") or "system",
                          "object_type": a.get("target_type"), "object_id": a.get("target_id"),
                          "object_name": name, "summary": summary}, AUDIT_HEADER))
    return AUDIT_HEADER, rows


def _dataset_versions(tenant_id: str, state: Dict[str, Any]) -> Tuple[List[str], List[List[str]]]:
    # Phiên bản dữ liệu `ds-xxxx` là bước 4 của kế hoạch; tới lúc đó bảng chỉ có tiêu đề.
    return DATASET_VERSION_HEADER, []


# ------------------------------------------------------------------ đồng bộ


def _is_daily_window(state: Dict[str, Any]) -> bool:
    """Lần đầu, hoặc đã tới giờ thấp điểm mà hôm nay chưa chạy."""
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo(DAILY_TZ))
    if "fp" not in state:
        return True
    return now.hour >= DAILY_HOUR and state.get("daily") != now.date().isoformat()


def _settled(last: Optional[datetime]) -> bool:
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).total_seconds() >= SETTLE_SECONDS


#: loại Sheet -> (cách lấy dấu vân tay, cách dựng dòng). Dấu vân tay None = loại
#: đổi hiếm, xét theo lịch hằng ngày.
def _tenant_sources(tenant_id: str) -> Dict[str, Tuple[Optional[Callable[[], Tuple[str, Any]]], Callable]]:
    def labels_fp():
        a, la = _fingerprint("classes", "class_uid", tenant_id, ("created_at", "deleted_at"))
        b, lb = _fingerprint("samples", "sample_uid", tenant_id, ("created_at", "updated_at", "deleted_at"))
        return f"{a}:{b}", max([t for t in (la, lb) if t], default=None)

    return {
        dl.SHEET_LABELS: (labels_fp, _labels),
        dl.SHEET_SAMPLES: (lambda: _fingerprint("samples", "sample_uid", tenant_id,
                                                ("created_at", "updated_at", "deleted_at")), _samples),
        dl.SHEET_VIDEOS: (lambda: _fingerprint("raw_uploads", "upload_uid", tenant_id,
                                               ("created_at", "updated_at", "deleted_at")), _videos),
        dl.SHEET_DATASET_VERSIONS: (lambda: ("v0", None), _dataset_versions),
        dl.SHEET_MODELS: (None, _models),
        dl.SHEET_AUDIT_LOGS: (None, _audit),
    }


def _sync_one(prefix: str, sheet_type: str, folder_id: str, fp_fn, build, force: bool = False) -> str:
    state = _load_state(prefix, sheet_type)
    daily = fp_fn is None
    if daily:
        if not force and not _is_daily_window(state):
            return "chua toi gio"
        fp, last = None, None
    else:
        fp, last = fp_fn()
        if not force and state.get("fp") == fp and state.get("sheet"):
            return "khong doi"
        if not force and state.get("fp") and not _settled(last):
            return "dang ghi, doi lan sau"
    sid, gid, created = _ensure_sheet(folder_id, dl.sheet_title(prefix, sheet_type), sheet_type.lower(), state)
    header, rows = build(state)
    how = _write(sid, gid, sheet_type.lower(), header, rows, state)
    state["fp"] = fp if not daily else hashlib.md5(json.dumps(state["matrix"]).encode()).hexdigest()
    if daily:
        from zoneinfo import ZoneInfo

        state["daily"] = datetime.now(ZoneInfo(DAILY_TZ)).date().isoformat()
    state["synced_at"] = datetime.now(timezone.utc).isoformat()
    _save_state(prefix, sheet_type, state)
    return ("tao moi, " if created else "") + how


def active_tenants() -> List[Dict[str, Any]]:
    return _db("SELECT tenant_id, slug, display_name, tenant_type, is_active, created_at FROM tenants "
               "WHERE deleted_at IS NULL AND (is_active OR tenant_type = 'COMMUNITY') ORDER BY created_at")


def tenant_prefix(tenant_id: str) -> str:
    root = dl.tenant_drive_root(tenant_id)
    return dl.COMMUNITY_PREFIX if root == dl.COMMUNITY_ROOT else root.rsplit("/", 1)[1]


def sync_tenant(tenant_id: str, *, force: bool = False) -> Dict[str, str]:
    folder_id = ensure_tenant_skeleton(tenant_id)
    prefix = tenant_prefix(tenant_id)
    result = {}
    for sheet_type, (fp_fn, build) in _tenant_sources(tenant_id).items():
        try:
            result[sheet_type] = _sync_one(prefix, sheet_type, folder_id, fp_fn,
                                           lambda st, b=build: b(tenant_id, st), force)
        except Exception as exc:  # một Sheet hỏng không chặn các Sheet còn lại
            logger.exception("[LOOKUP] %s - %s failed", prefix, sheet_type)
            result[sheet_type] = f"LOI: {exc}"
    return result


def _platform_tenants(state: Dict[str, Any]) -> Tuple[List[str], List[List[str]]]:
    rows = []
    for t in active_tenants():
        tid = t["tenant_id"]
        stats = _db(
            "SELECT (SELECT count(*) FROM tenant_members WHERE tenant_id = %s) AS members, "
            "(SELECT count(*) FROM classes WHERE tenant_id = %s AND deleted_at IS NULL) AS labels, "
            "(SELECT count(*) FROM samples WHERE tenant_id = %s AND deleted_at IS NULL) AS samples, "
            "(SELECT count(*) FROM raw_uploads WHERE tenant_id = %s AND deleted_at IS NULL) AS videos, "
            "(SELECT bytes_used FROM tenant_storage WHERE tenant_id = %s) AS bytes, "
            "(SELECT max(created_at) FROM samples WHERE tenant_id = %s) AS last",
            (tid,) * 6)[0]
        published = [f"{r['model_name']} {r['version']}" for r in _model_rows(tid) if r["status"] == "published"]
        root_id = _client().resolve_folder_path(dl.tenant_drive_root(tid), create_missing=False)
        rows.append(_row({
            "tenant_id": tid, "display_name": t.get("display_name"), "tenant_type": t.get("tenant_type"),
            "status": "active" if t.get("is_active") else "inactive", "created_at": t.get("created_at"),
            "member_count": stats["members"], "label_count": stats["labels"], "sample_count": stats["samples"],
            "video_count": stats["videos"], "storage_bytes": stats["bytes"],
            "published_models": ", ".join(published), "last_activity_at": stats["last"],
            "storage_url": FOLDER_URL.format(root_id) if root_id else "",
        }, TENANT_HEADER))
    return TENANT_HEADER, rows


def _platform_layout(state: Dict[str, Any]) -> Tuple[List[str], List[List[str]]]:
    """Bảng giải thích cây thư mục cho NGƯỜI đọc: lời thường, không cú pháp mẫu.

    Mỗi dòng là một thư mục có thật; `storage_url` mở đúng thư mục ví dụ đó.
    """
    T, C, L = dl.TENANTS_ROOT, dl.COMMUNITY_ROOT, dl.LOOKUP_LIST_DIRNAME
    S, V, M = (dl.DRIVE_TREE_NAMES[t] for t in (dl.FEATURES_TREE, dl.RAW_VIDEOS_TREE, dl.MODELS_TREE))
    ver, since = LAYOUT_VERSION
    client = _client()
    tenants = [t for t in active_tenants() if dl.tenant_drive_root(t["tenant_id"]) != C]
    sample_root = dl.tenant_drive_root(tenants[0]["tenant_id"]) if tenants else f"{T}"

    def url(path: str) -> str:
        fid = client.resolve_folder_path(path, create_missing=False) if path else client.root_folder_id
        return FOLDER_URL.format(fid) if fid else ""

    system = "Hệ thống tự ghi"
    spec = [
        (f"{L}", "Bảng tra cứu cho toàn nền tảng: danh sách tổ chức và bảng giải thích này.",
         system, f"Tên bảng bắt đầu bằng \"{dl.PLATFORM_PREFIX} - \"", L),
        ("SOT", "Gói dữ liệu có chữ ký số, dùng để khôi phục và đối chiếu.",
         "Máy phát hành SOT", "Mỗi lần phát hành một thư mục \"Ver<số>_<ngày>\"", "SOT"),
        (f"{C}", "Kho dùng chung của VOYA (cộng đồng).", system, "Tên cố định", C),
        (f"{T}", "Mỗi tổ chức một thư mục con.", system,
         "Tên thư mục con là mã tổ chức: không dấu, chữ thường, nối bằng gạch ngang, không trùng", T),
        (f"{C} hoặc {T} › (tổ chức) › {L}", "Bảng tra cứu của riêng tổ chức đó: nhãn, mẫu, video, "
         "phiên bản dữ liệu, mô hình, nhật ký.", system, "Tên bảng bắt đầu bằng mã tổ chức, ví dụ "
         f"\"{dl.sheet_title(dl.COMMUNITY_PREFIX, dl.SHEET_SAMPLES)}\"", f"{C}/{L}"),
        (f"(tổ chức) › {S}", "Mẫu đã xử lý (tệp .npz), xếp theo ngôn ngữ › phương ngữ › nhãn.",
         system, "Mỗi nhãn một thư mục \"class_<nhãn>_<mã>\", mỗi mẫu một tệp \"sample_<mã>.npz\"",
         f"{sample_root}/{S}"),
        (f"(tổ chức) › {V}", "Video gốc người dùng tải lên, xếp như Samples.", system,
         "Tên tệp là mã video + tên tệp gốc", f"{C}/{V}"),
        (f"(tổ chức) › {M}", "Mô hình đã phát hành, mỗi mô hình một thư mục.", system,
         "Mỗi lần phát hành một thư mục con", f"{C}/{M}"),
    ]
    return LAYOUT_HEADER, [[folder, contents, who, rule, url(path), ver, since]
                           for folder, contents, who, rule, path in spec]


def sync_platform(*, force: bool = False) -> Dict[str, str]:
    folder_id = _client().resolve_folder_path(dl.LOOKUP_LIST_DIRNAME, create_missing=True)
    result = {}
    for sheet_type, build in ((dl.SHEET_TENANTS, _platform_tenants), (dl.SHEET_STORAGE_LAYOUT, _platform_layout)):
        try:
            result[sheet_type] = _sync_one(dl.PLATFORM_PREFIX, sheet_type, folder_id, None, build, force)
        except Exception as exc:
            logger.exception("[LOOKUP] platform - %s failed", sheet_type)
            result[sheet_type] = f"LOI: {exc}"
    return result


def sync_all(*, force: bool = False) -> Dict[str, Dict[str, str]]:
    """Mọi tổ chức đang hoạt động + Sheet của nền tảng. Gọi lại bao nhiêu lần cũng được."""
    if dl.current_layout() != dl.TENANT:
        return {"_": {"skipped": "GDRIVE_LAYOUT khong phai tenant"}}
    out = {}
    for t in active_tenants():
        try:
            out[t["tenant_id"]] = sync_tenant(t["tenant_id"], force=force)
        except Exception as exc:
            logger.exception("[LOOKUP] tenant %s failed", t["tenant_id"])
            out[t["tenant_id"]] = {"_": f"LOI: {exc}"}
    out["platform"] = sync_platform(force=force)
    return out
