import os
import shutil
from pathlib import Path
from filelock import FileLock
import csv

from app.config import settings
from app.dataset_manager import MASTER_LABELS, LABEL_FIELDS
from app.dataset_samples import SAMPLES_CSV, SAMPLE_FIELDS
from app.raw_uploads import RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS
from app.storage.metadata_db import _get_conn
from app.storage.gdrive_client import get_gdrive_client
from app.catalog_sync import _catalog_lock, _write_csv

def hard_delete_classes(slugs_to_delete):
    print(f"Hard deleting classes matching slugs: {slugs_to_delete}")
    
    with _catalog_lock():
        # 1. Read labels
        with open(MASTER_LABELS, newline="", encoding="utf-8") as f:
            labels = list(csv.DictReader(f))
        
        to_delete_uids = []
        new_labels = []
        for r in labels:
            if any(slug in r['slug'].lower() for slug in slugs_to_delete):
                to_delete_uids.append(r['class_uid'])
                print(f"Deleting label: {r['slug']} ({r['class_uid']})")
                
                # Delete from GDrive
                try:
                    client = get_gdrive_client()
                    fid = client.resolve_folder_path(f"features/{r['language']}/{r['dialect']}/{r['folder_name']}")
                    if fid:
                        client.service.files().delete(fileId=fid).execute()
                        print(f"Deleted folder features/.../{r['folder_name']} from GDrive")
                except Exception as e:
                    print(f"GDrive delete failed for {r['folder_name']}: {e}")

                # Delete local features folder
                feature_dir = Path("/dataset/features") / r['language'] / r['dialect'] / r['folder_name']
                if feature_dir.exists():
                    shutil.rmtree(feature_dir, ignore_errors=True)
                    print(f"Deleted local features: {feature_dir}")

                # Delete local raw folder
                raw_dir = Path("/dataset/raw_videos") / r['language'] / r['dialect'] / r['folder_name']
                if raw_dir.exists():
                    shutil.rmtree(raw_dir, ignore_errors=True)
                    print(f"Deleted local raw: {raw_dir}")
            else:
                new_labels.append(r)
        
        if not to_delete_uids:
            print("No classes found to delete.")
            return

        # 2. Write labels back
        _write_csv(MASTER_LABELS, LABEL_FIELDS, new_labels)
        
        # 3. Read & filter samples
        if SAMPLES_CSV.exists():
            with open(SAMPLES_CSV, newline="", encoding="utf-8") as f:
                samples = list(csv.DictReader(f))
            new_samples = [s for s in samples if s.get('class_uid') not in to_delete_uids]
            _write_csv(SAMPLES_CSV, SAMPLE_FIELDS, new_samples)
            print(f"Deleted {len(samples) - len(new_samples)} samples from CSV")
        
        # 4. Read & filter raw uploads
        if RAW_UPLOADS_CSV.exists():
            with open(RAW_UPLOADS_CSV, newline="", encoding="utf-8") as f:
                raws = list(csv.DictReader(f))
            new_raws = [r for r in raws if r.get('class_uid') not in to_delete_uids]
            _write_csv(RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS, new_raws)
            print(f"Deleted {len(raws) - len(new_raws)} raw uploads from CSV")
        
        # 5. DB deletion
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                for uid in to_delete_uids:
                    cur.execute("DELETE FROM raw_uploads WHERE class_uid = %s", (uid,))
                    cur.execute("DELETE FROM samples WHERE class_uid = %s", (uid,))
                    cur.execute("DELETE FROM classes WHERE class_uid = %s", (uid,))
            conn.commit()
            print("Deleted from PostgreSQL.")
        except Exception as e:
            conn.rollback()
            print(f"DB delete failed: {e}")
        finally:
            conn.close()
            
    # Trigger sheets sync
    from app.export_tasks import export_labels_to_sheets, export_samples_to_sheets
    export_labels_to_sheets.delay()
    export_samples_to_sheets.delay()
    print("Triggered Sheets Sync")

if __name__ == "__main__":
    hard_delete_classes(["ahaaa1", "ahahaa123"])
