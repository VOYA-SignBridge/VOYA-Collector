"""Merging one dialect into another, across every layer that stores it.

A dialect_id is not a column — it is a key in Postgres, in three CSVs, in two
directory trees, in a sidecar JSON beside every single .npz, and on Drive. It is
ALSO baked into checkpoint filenames and published split manifests, which are
records of experiments that already ran and must never be rewritten; those stay
resolvable through the dialect_aliases table instead.

Order is deliberate — cheap and reversible first, expensive and remote last:

    Postgres (one transaction) -> CSV -> local dirs -> sidecars -> Drive

Going the other way is how orphans are made. Every step after the first is
idempotent, so a retry resumes instead of duplicating.

See docs/02-data/DIALECT_LIFECYCLE.md §3.5.
"""

from __future__ import annotations

import csv
import json
import logging
import shutil
from pathlib import Path
from typing import Dict

from filelock import FileLock, Timeout

from app.config import settings
from app.worker import celery_app

logger = logging.getLogger(__name__)

_CSV_TARGETS = (
    ("labels.csv", "dataset"),
    ("samples.csv", "dataset"),
    ("raw_videos/uploads.csv", "dataset"),
)


def _rewrite_csv(path: Path, old: str, new: str) -> int:
    """Swap dialect + any path cell that embeds it. Returns rows changed."""
    if not path.is_file():
        return 0
    try:
        lock = FileLock(str(path) + ".lock", timeout=30)
        with lock:
            with path.open(newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                rows, cols = list(reader), list(reader.fieldnames or [])
            n = 0
            for r in rows:
                if (r.get("dialect") or "").strip() != old:
                    continue
                r["dialect"] = new
                for cell in ("file_path", "storage_key"):
                    v = r.get(cell) or ""
                    if f"/{old}/" in v:
                        r[cell] = v.replace(f"/{old}/", f"/{new}/")
                n += 1
            if n:
                tmp = path.with_suffix(path.suffix + ".tmp")
                with tmp.open("w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", restval="")
                    w.writeheader()
                    w.writerows(rows)
                tmp.replace(path)
            return n
    except Timeout:
        logger.warning("[MERGE] %s đang bị khoá — sẽ thử lại", path)
        raise


def _move_tree(root: Path, old: str, new: str) -> int:
    """features/<lang>/<old>/* -> features/<lang>/<new>/. Idempotent."""
    moved = 0
    if not root.is_dir():
        return 0
    for lang_dir in root.iterdir():
        src, dst = lang_dir / old, lang_dir / new
        if not src.is_dir():
            continue
        dst.mkdir(parents=True, exist_ok=True)
        for child in list(src.iterdir()):
            target = dst / child.name
            if target.exists():
                # Already moved by an earlier attempt; drop the leftover source.
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
                continue
            shutil.move(str(child), str(target))
            moved += 1
        try:
            src.rmdir()
        except OSError:
            pass
    return moved


def _rewrite_sidecars(root: Path, new: str, old: str) -> int:
    """The layer everyone forgets: one JSON per class AND one per sample."""
    n = 0
    for path in root.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or (data.get("dialect") or "") != old:
            continue
        data["dialect"] = new
        for cell in ("file_path", "storage_key"):
            v = data.get(cell)
            if isinstance(v, str) and f"/{old}/" in v:
                data[cell] = v.replace(f"/{old}/", f"/{new}/")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        n += 1
    return n


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def merge_dialect_task(self, old_id: str, new_id: str) -> Dict[str, int]:
    """Move every row and file from `old_id` to `new_id`.

    The catalogue half (alias row + retiring the old dialect) is done
    synchronously by the caller before this runs, so the registry is already
    consistent even if this task is still working — nothing points at a dialect
    that no longer resolves.
    """
    if not old_id or not new_id or old_id == new_id:
        return {"skipped": 1}

    from app.storage.metadata_db import _execute

    report: Dict[str, int] = {}
    root = settings.dataset_root

    # 1. Postgres — one statement per table, all inside psycopg's transaction.
    for table in ("classes", "samples", "raw_uploads"):
        _execute(f"UPDATE {table} SET dialect = %s WHERE dialect = %s", (new_id, old_id))
    for table in ("samples", "raw_uploads"):
        for col in ("file_path", "storage_key"):
            _execute(
                f"UPDATE {table} SET {col} = replace({col}, %s, %s) WHERE {col} LIKE %s",
                (f"/{old_id}/", f"/{new_id}/", f"%/{old_id}/%"),
            )
    logger.info("[MERGE] %s -> %s: Postgres xong", old_id, new_id)

    try:
        # 2. CSV
        for name, _ in _CSV_TARGETS:
            report[f"csv:{name}"] = _rewrite_csv(root / name, old_id, new_id)

        # 3. Local trees (both of them — raw_videos is the one that gets missed)
        report["moved_features"] = _move_tree(root / "features", old_id, new_id)
        report["moved_raw_videos"] = _move_tree(root / "raw_videos", old_id, new_id)

        # 4. Sidecars — slowest and least urgent: nothing serves a request from them.
        report["sidecars"] = _rewrite_sidecars(root / "features", new_id, old_id)
    except Exception as exc:
        logger.exception("[MERGE] %s -> %s dừng giữa chừng: %s", old_id, new_id, exc)
        raise self.retry(exc=exc)

    # 5. Drive — remote, no transaction, never blocks the answer to the admin.
    try:
        from app.export_tasks import move_gdrive_paths_task

        move_gdrive_paths_task.delay(pairs=[(f"features/*/{old_id}", f"features/*/{new_id}")])
    except Exception as exc:
        logger.warning("[MERGE] Drive move dispatch thất bại (dữ liệu cục bộ đã đúng): %s", exc)

    logger.info("[MERGE] %s -> %s hoàn tất: %s", old_id, new_id, report)
    return report
