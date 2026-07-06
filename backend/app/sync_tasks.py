import os
import logging
from pathlib import Path
from typing import List, Dict, Any

from app.worker import celery_app
from app.config import settings
from app.storage.postgres_connection import connect_postgres
from psycopg2.extras import RealDictCursor
from app.storage.gdrive_client import download_from_gdrive

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def download_missing_files_to_local(self):
    """
    Scans the database for samples and raw_uploads that have a storage_url
    but are missing their local files on disk. Downloads them from GDrive.
    """
    logger.info("[SYNC] Starting download_missing_files_to_local task")
    conn = connect_postgres()
    try:
        downloaded_count = 0
        skipped_count = 0
        error_count = 0
        current_progress = 0

        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Fetch Features
                cur.execute(
                    """
                    SELECT sample_uid, file_path, storage_url 
                    FROM samples 
                    WHERE storage_url IS NOT NULL AND storage_url != '' AND deleted_at IS NULL
                    """
                )
                samples = cur.fetchall()
                
                # 2. Fetch Raw Videos
                cur.execute(
                    """
                    SELECT upload_uid, local_path, storage_url 
                    FROM raw_uploads 
                    WHERE storage_url IS NOT NULL AND storage_url != '' AND deleted_at IS NULL
                    """
                )
                raw_uploads = cur.fetchall()
                
                total_items = len(samples) + len(raw_uploads)
                
                def report_progress():
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": current_progress,
                            "total": total_items,
                            "downloaded": downloaded_count,
                            "skipped": skipped_count,
                            "errors": error_count
                        }
                    )
                
                report_progress()
                
                # Process Features
                for sample in samples:
                    storage_url = sample["storage_url"]
                    file_path = sample["file_path"]
                    
                    # Resilient check in case they are swapped in the DB
                    if file_path and (file_path.startswith("http") or file_path.startswith("gdrive://")):
                        if storage_url and not (storage_url.startswith("http") or storage_url.startswith("gdrive://")):
                            # Swap them back
                            storage_url, file_path = file_path, storage_url
                        else:
                            # Both are URLs? We can't determine the local path
                            file_path = None
                    
                    if not file_path or not storage_url:
                        current_progress += 1
                        report_progress()
                        continue
                        
                    local_abs_path = Path(settings.dataset_root) / file_path
                    
                    if local_abs_path.exists():
                        skipped_count += 1
                    else:
                        try:
                            logger.info(f"[SYNC] Downloading feature for {sample['sample_uid']} from {storage_url}")
                            local_abs_path.parent.mkdir(parents=True, exist_ok=True)
                            download_from_gdrive(storage_url, str(local_abs_path))
                            downloaded_count += 1
                        except Exception as e:
                            logger.error(f"[SYNC] Failed to download feature {sample['sample_uid']}: {e}")
                            error_count += 1
                            
                    current_progress += 1
                    report_progress()

                # Process Raw Videos
                for raw in raw_uploads:
                    storage_url = raw["storage_url"]
                    local_path = raw["local_path"]
                    
                    # Resilient check in case they are swapped in the DB
                    if local_path and (local_path.startswith("http") or local_path.startswith("gdrive://")):
                        if storage_url and not (storage_url.startswith("http") or storage_url.startswith("gdrive://")):
                            # Swap them back
                            storage_url, local_path = local_path, storage_url
                        else:
                            # Both are URLs? We can't determine the local path
                            local_path = None
                            
                    if not local_path or not storage_url:
                        current_progress += 1
                        report_progress()
                        continue
                        
                    local_abs_path = Path(local_path)
                    if not local_abs_path.is_absolute():
                         local_abs_path = Path(settings.dataset_root) / local_path
                         
                    if local_abs_path.exists():
                        skipped_count += 1
                    else:
                        try:
                            logger.info(f"[SYNC] Downloading raw video for {raw['upload_uid']} from {storage_url}")
                            local_abs_path.parent.mkdir(parents=True, exist_ok=True)
                            download_from_gdrive(storage_url, str(local_abs_path))
                            downloaded_count += 1
                        except Exception as e:
                            logger.error(f"[SYNC] Failed to download raw video {raw['upload_uid']}: {e}")
                            error_count += 1
                            
                    current_progress += 1
                    report_progress()

        logger.info(f"[SYNC] Finished. Downloaded: {downloaded_count}, Skipped: {skipped_count}, Errors: {error_count}")
        return {
            "status": "completed",
            "current": current_progress,
            "total": total_items,
            "downloaded": downloaded_count,
            "skipped": skipped_count,
            "errors": error_count
        }

    except Exception as e:
        logger.exception("[SYNC] Critical error in download_missing_files_to_local task")
        raise
    finally:
        conn.close()
