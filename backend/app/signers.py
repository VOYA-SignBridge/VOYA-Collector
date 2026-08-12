"""Normalized signer registry (vocabulary schema v2).

signer_id (S001, S002, ...) is the ONLY key research code may use for
signer-disjoint evaluation. Free-text display names are for humans only.

Storage: dataset/signers.csv (FileLock-guarded, same pattern as labels.csv),
best-effort mirrored to the Postgres `signers` table. New live-capture samples
resolve their signer from the AUTHENTICATED user (external_user_id = auth user
id) — never from free-text input.
"""

from __future__ import annotations

import csv
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from filelock import FileLock

from app.config import settings

logger = logging.getLogger(__name__)

SIGNERS_CSV: Path = settings.dataset_root / "signers.csv"
SIGNER_FIELDS = ["signer_id", "display_name", "regional_group", "external_user_id", "is_active", "created_at"]


def _now_str() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_rows_locked() -> List[Dict[str, str]]:
    if not SIGNERS_CSV.exists():
        return []
    with SIGNERS_CSV.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_rows_locked(rows: List[Dict[str, str]]) -> None:
    SIGNERS_CSV.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="signers_", suffix=".csv", dir=str(SIGNERS_CSV.parent))
    os.close(fd)
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=SIGNER_FIELDS, extrasaction="ignore", restval="")
            w.writeheader()
            w.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, SIGNERS_CSV)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


# IDs below this belong to the legacy hand-curated namespace in
# config/legacy_signer_mapping.json (S001..S0xx, one key per confirmed
# real-world person). That file is a research-side artifact and is NOT mounted
# into the backend container, so this process cannot read it to avoid a clash.
# Allocating from S101 upwards keeps the two namespaces disjoint by
# construction: without it the registry hands out S012 to the next new account
# while the legacy table already means "Nhung" by S012, and any row that falls
# back to signer_id would silently join two different people under one key.
REGISTRY_ID_FLOOR = 100


def _next_signer_id(rows: List[Dict[str, str]]) -> str:
    max_n = REGISTRY_ID_FLOOR
    for r in rows:
        sid = (r.get("signer_id") or "").strip()
        if sid.startswith("S") and sid[1:].isdigit():
            max_n = max(max_n, int(sid[1:]))
    return f"S{max_n + 1:03d}"


def list_signers() -> List[Dict[str, str]]:
    lock = FileLock(str(SIGNERS_CSV) + ".lock")
    with lock:
        return _load_rows_locked()


def resolve_signer_for_user(current_user: Dict[str, object]) -> str:
    """Return the stable signer_id for an authenticated user, creating a
    registry entry on first contribution.

    Matching is by external_user_id (auth UUID) ONLY — display names are never
    used as identity, so 'Tran'/'Trân'/'trân' can each map wherever their auth
    accounts point without any string heuristics.
    """
    external_id = str(current_user.get("id") or "").strip()
    display_name = str(current_user.get("username") or "").strip()
    if not external_id:
        return ""

    lock = FileLock(str(SIGNERS_CSV) + ".lock")
    with lock:
        rows = _load_rows_locked()
        for r in rows:
            if (r.get("external_user_id") or "").strip() == external_id:
                return (r.get("signer_id") or "").strip()

        new_row = {
            "signer_id": _next_signer_id(rows),
            "display_name": display_name,
            "regional_group": "",
            "external_user_id": external_id,
            "is_active": "1",
            "created_at": _now_str(),
        }
        rows.append(new_row)
        _write_rows_locked(rows)

    logger.info("[SIGNER] registered %s for auth user %s (%s)",
                new_row["signer_id"], external_id, display_name)
    try:
        from app.storage.metadata_db import upsert_signer
        upsert_signer(new_row)
    except Exception as exc:
        logger.warning("[SIGNER] DB mirror failed: %s", exc)

    # Hồ sơ người ký vừa lập xong — giờ mới có chỗ để treo đồng thuận.
    #
    # Thứ tự này là thứ tự thật và không đảo được: người ta bấm đồng ý ở màn
    # hình pháp lý (ghi vào `user_consents`) TRƯỚC, có khi hàng tuần trước, rồi
    # mới đóng góp mẫu đầu tiên. Lúc bấm đồng ý chưa có hàng nào trong `signers`
    # để `sync_signer_consent` gắn vào, nên nó ghi log rồi bỏ qua. Đây là nửa
    # còn lại: gọi lại ngay sau khi lập hồ sơ, để chấp thuận đã ký từ trước
    # được áp cho mẫu ĐẦU TIÊN chứ không phải từ mẫu thứ hai trở đi.
    try:
        from app.consent_gate import CONSENT_DOCUMENT_SCOPE, sync_signer_consent
        from app.legal import has_consent

        for kind in CONSENT_DOCUMENT_SCOPE:
            if has_consent(external_id, kind):
                sync_signer_consent(external_id, kind)
    except Exception as exc:
        logger.warning("[SIGNER] consent backfill for %s failed: %s",
                       new_row["signer_id"], exc)
    return new_row["signer_id"]


def get_signer(signer_id: str) -> Optional[Dict[str, str]]:
    for r in list_signers():
        if (r.get("signer_id") or "").strip() == signer_id:
            return r
    return None
