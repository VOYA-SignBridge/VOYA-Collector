import re
from pathlib import Path

catalog_sync_path = Path("backend/app/catalog_sync.py")
content = catalog_sync_path.read_text("utf-8")

fork_func = """
def sync_fork_class_for_user(class_idx: int | str, payload: dict, user_id: str) -> dict:
    ensure_tables()
    op_id = f"class_fork_{class_idx}_{user_id}"
    slog.start_operation(op_id)
    
    with _catalog_lock():
        rows = load_labels()
        target_row = _find_class_row_by_ref(rows, class_idx)
        if not target_row:
            raise CatalogSyncError("Class not found", status_code=404)
            
        old_meta = _build_class_meta_from_row(target_row)
        new_label = payload.get("label_original", "").strip()
        
        from app.dataset_manager import get_or_register_class
        new_meta = get_or_register_class(
            label_original=new_label,
            language=old_meta.language,
            dialect=old_meta.dialect,
            is_common_global=old_meta.is_common_global,
            is_common_language=old_meta.is_common_language,
        )
        
        from app.dataset_samples import list_samples
        from app.dataset_raw_uploads import list_raw_uploads
        all_samples = list_samples()
        all_raw = list_raw_uploads()
        
        sample_rows_after = []
        changed_samples = []
        for s in all_samples:
            if s.get("class_uid") == old_meta.class_uid and s.get("user_id") == user_id:
                new_s = dict(s)
                old_file_path = _resolve_sample_file_path(s)
                if old_file_path and old_file_path.exists():
                    new_feature_dir = new_meta.hierarchy_path()
                    new_feature_dir.mkdir(parents=True, exist_ok=True)
                    new_file_path = new_feature_dir / old_file_path.name
                    import shutil
                    shutil.move(str(old_file_path), str(new_file_path))
                    new_s["file_path"] = str(new_file_path)
                    new_s["storage_key"] = _dataset_storage_key(new_file_path) or new_s.get("storage_key", "")
                    new_s["storage_url"] = str(new_file_path)
                    _update_sample_metadata_json(new_file_path, new_meta)
                
                new_s.update({
                    "class_uid": new_meta.class_uid,
                    "slug": new_meta.slug,
                    "label_original": new_meta.label_original,
                    "language": new_meta.language,
                    "dialect": new_meta.dialect,
                })
                changed_samples.append(new_s)
                sample_rows_after.append(new_s)
            else:
                sample_rows_after.append(s)
                
        raw_rows_after = []
        changed_raw = []
        for r in all_raw:
            if r.get("class_uid") == old_meta.class_uid and r.get("user_id") == user_id:
                new_r = dict(r)
                old_local_path = Path(r.get("local_path") or r.get("storage_url") or "") if (r.get("local_path") or r.get("storage_url")) else None
                if old_local_path and old_local_path.exists():
                    new_raw_dir = Path(settings.dataset_root) / "raw_videos" / new_meta.language / new_meta.dialect / new_meta.folder_name()
                    new_raw_dir.mkdir(parents=True, exist_ok=True)
                    new_local_path = new_raw_dir / old_local_path.name
                    import shutil
                    shutil.move(str(old_local_path), str(new_local_path))
                    new_r["local_path"] = str(new_local_path)
                    new_r["storage_url"] = str(new_local_path)
                
                new_r.update({
                    "class_uid": new_meta.class_uid,
                    "slug": new_meta.slug,
                    "label_original": new_meta.label_original,
                    "language": new_meta.language,
                    "dialect": new_meta.dialect,
                })
                changed_raw.append(new_r)
                raw_rows_after.append(new_r)
            else:
                raw_rows_after.append(r)
                
        from app.dataset_manager import _write_csv
        _write_csv(Path(settings.dataset_root) / "samples.csv", sample_rows_after, list(sample_rows_after[0].keys()) if sample_rows_after else [])
        _write_csv(Path(settings.dataset_root) / "raw_uploads.csv", raw_rows_after, list(raw_rows_after[0].keys()) if raw_rows_after else [])
        
        _sync_db_samples(changed_samples)
        _sync_db_raw_uploads(changed_raw)
        
        # also sync the new class to db
        new_class_row = _find_class_row_by_ref(load_labels(), new_meta.class_uid)
        if new_class_row:
            _sync_db_class(new_class_row)
            
    slog.log_operation(
        OperationType.CLASS_UPDATE,
        OperationStatus.SUCCESS,
        {"action": "fork", "class_idx": old_meta.class_idx, "new_class_uid": new_meta.class_uid},
        duration_ms=slog.end_operation(op_id),
    )
    return {"changed": True, "forked": True, "new_class_uid": new_meta.class_uid, "samples_moved": len(changed_samples)}
"""

if "def sync_fork_class_for_user" not in content:
    content += "\n" + fork_func
    catalog_sync_path.write_text(content, "utf-8")
    print("Injected fork logic into catalog_sync.py")
