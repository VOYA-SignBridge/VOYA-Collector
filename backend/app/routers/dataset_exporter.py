from fastapi import APIRouter, HTTPException
from pathlib import Path
from ..processing.utils import load_npz_features, merge_memmap
from ..processing import validator
from fastapi import Query
from app.config import settings
from app.dataset_samples import list_samples as list_samples_v2
from app.storage.gdrive_client import materialize_sample_artifacts

router = APIRouter(prefix="/api/dataset", tags=["Dataset Exporter"])

BASE_DATASET_DIR = Path(settings.dataset_root) / "features"
OUTPUT_DIR = Path(settings.dataset_root) / "processed" / "memmap"
CACHE_EXPORT_DIR = Path(settings.dataset_root) / "cache" / "export_materialized"


def _has_npz_files(base_dir: Path) -> bool:
    return base_dir.exists() and any(base_dir.rglob("*.npz"))


@router.post("/export")
def export_dataset(fix: bool = Query(False, description="Attempt to auto-fix mismatched samples (pad/truncate) before export")):
    """Aggregate all processed .npz files into unified memmap dataset"""
    try:
        # Materialize Google Drive-backed rows into a local cache so export can
        # use the same code path as local files.
        rows = list_samples_v2()
        remote_rows = []
        for row in rows:
            source = str(row.get("file_path") or row.get("storage_url") or "").strip()
            if source.startswith(("gdrive://", "https://drive.google.com")):
                remote_rows.append(row)

        if remote_rows:
            materialize_sample_artifacts(remote_rows, CACHE_EXPORT_DIR)

        validation_reports = []
        if _has_npz_files(BASE_DATASET_DIR):
            local_report = validator.validate_samples(BASE_DATASET_DIR, expected_T=60, expected_D=126, fix=fix)
            validation_reports.append({"scope": "local", **local_report})

        if _has_npz_files(CACHE_EXPORT_DIR):
            remote_report = validator.validate_samples(CACHE_EXPORT_DIR, expected_T=60, expected_D=126, fix=fix)
            validation_reports.append({"scope": "remote", **remote_report})

        if not validation_reports:
            raise HTTPException(status_code=404, detail="No valid samples found.")

        if any((not r.get("ok", False)) and r.get("fixed_count", 0) == 0 for r in validation_reports):
            raise HTTPException(status_code=400, detail={"message": "Validation failed", "report": validation_reports})

        local_samples = load_npz_features(BASE_DATASET_DIR) if _has_npz_files(BASE_DATASET_DIR) else []
        remote_samples = load_npz_features(CACHE_EXPORT_DIR) if _has_npz_files(CACHE_EXPORT_DIR) else []
        samples = local_samples + remote_samples
        if not samples:
            raise HTTPException(status_code=404, detail="No valid samples found.")
        meta = merge_memmap(samples, OUTPUT_DIR)
        return {
            "status": "success",
            "message": f"Exported {meta['total_samples']} samples.",
            "validation_report": {"ok": all(r.get("ok", False) for r in validation_reports), "sources": validation_reports},
            "output": meta
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
