#!/usr/bin/env python
"""
Audit script for Drive files before cleanup.
Compares labels2.0.csv, samples2.0.csv, and class folders against current local state.
"""

import os
import sys
import csv
import logging
from pathlib import Path
from typing import Set, Dict, List, Tuple

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.config import settings
from app.storage.gdrive_client import GoogleDriveClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_local_samples() -> Set[str]:
    """Load active class folder names from local samples.csv"""
    active_classes = set()
    samples_csv = Path(__file__).parent / 'dataset' / 'samples' / 'samples.csv'
    
    if not samples_csv.exists():
        logger.warning(f"Samples CSV not found: {samples_csv}")
        return active_classes
    
    with open(samples_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('dialect') == 'hoa-de':
                storage_key = row.get('storage_key', '')
                # storage_key format: features/vn/hoa-de/class_rang-muoi_9cc07248/sample_xxx.npz
                if storage_key:
                    parts = storage_key.split('/')
                    if len(parts) >= 4:
                        class_folder = parts[3]  # e.g., "class_rang-muoi_9cc07248"
                        active_classes.add(class_folder)
    
    logger.info(f"Found {len(active_classes)} active class folders in local samples.csv")
    return active_classes


def load_local_labels() -> Dict[str, str]:
    """Load active labels from local labels_dialect.csv"""
    labels = {}
    labels_csv = Path(__file__).parent / 'dataset' / 'labels' / 'labels_dialect.csv'
    
    if not labels_csv.exists():
        logger.warning(f"Labels CSV not found: {labels_csv}")
        return labels
    
    with open(labels_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('dialect') == 'hoa-de':
                slug = row.get('slug', '')
                label_uid = row.get('class_uid', '')
                if slug and label_uid:
                    labels[slug] = label_uid
    
    logger.info(f"Found {len(labels)} active labels in local labels_dialect.csv")
    return labels


def list_drive_items(client: GoogleDriveClient, path: str) -> List[Tuple[str, str, str]]:
    """
    List items in a Drive folder path.
    Returns: List of (name, item_id, mime_type)
    """
    items = []
    try:
        folder_id = client.resolve_folder_path(path, create_missing=False)
        if not folder_id:
            logger.warning(f"Folder not found on Drive: {path}")
            return items
        
        query = f"'{folder_id}' in parents and trashed=false"
        results = client.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, mimeType, modifiedTime)',
            pageSize=1000
        ).execute()
        
        for item in results.get('files', []):
            items.append((item['name'], item['id'], item.get('mimeType', '')))
        
        logger.info(f"Listed {len(items)} items in Drive path: {path}")
    except Exception as e:
        logger.error(f"Error listing Drive items at {path}: {e}")
    
    return items


def audit_drive_files():
    """Main audit function"""
    logger.info("=" * 80)
    logger.info("STARTING DRIVE FILES AUDIT")
    logger.info("=" * 80)
    
    # Initialize Drive client
    credentials_path = Path(__file__).parent / 'gdrive' / 'credentials.json'
    token_path = Path(__file__).parent / 'gdrive' / 'token.json'
    
    if not credentials_path.exists():
        logger.error(f"Credentials file not found: {credentials_path}")
        return
    
    try:
        client = GoogleDriveClient(
            credentials_path=str(credentials_path),
            token_path=str(token_path),
            root_folder_id=settings.gdrive_root_folder_id
        )
    except Exception as e:
        logger.error(f"Failed to initialize Drive client: {e}")
        return
    
    # Load local state
    active_samples = load_local_samples()
    active_labels = load_local_labels()
    
    # Audit results
    audit_report = []
    
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1: CSV FILES AUDIT (labels2.0.csv, samples2.0.csv)")
    logger.info("=" * 80)
    
    # Check root level CSVs
    try:
        root_items = list_drive_items(client, 'signbridge-storage')
        for name, item_id, mime_type in root_items:
            if name in ['labels2.0.csv', 'samples2.0.csv']:
                decision = "[KEEP]" if name in ['labels2.0.csv', 'samples2.0.csv'] else "[DELETE]"
                msg = f"{decision} {name} - CSV catalog file (always keep)"
                logger.info(msg)
                audit_report.append(msg)
    except Exception as e:
        logger.error(f"Error checking root CSVs: {e}")
    
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 2: CLASS FOLDERS AUDIT (features/vn/hoa-de/)")
    logger.info("=" * 80)
    logger.info(f"Active class folders in local samples.csv: {len(active_samples)}")
    for cf in sorted(active_samples):
        logger.info(f"  - {cf}")
    
    # List Drive class folders
    drive_classes = list_drive_items(client, 'features/vn/hoa-de')
    
    logger.info(f"\nClass folders found on Drive: {len(drive_classes)}")
    audit_report.append(f"\n[PHASE 2] CLASS FOLDERS - {len(drive_classes)} folders found on Drive\n")
    
    deleted_count = 0
    kept_count = 0
    
    for name, item_id, mime_type in sorted(drive_classes, key=lambda x: x[0]):
        if not name.startswith('class_'):
            # Skip non-class items (like CSVs)
            audit_report.append(f"[SKIP] {name} - Not a class folder")
            continue
        
        # Check if it's class_z_* (DELETE ONLY THESE)
        if name.startswith('class_z_'):
            decision = "[DELETE]"
            reason = "Class with letter 'z' - marked for deletion per audit rule"
            deleted_count += 1
        elif name in active_samples:
            decision = "[KEEP]"
            reason = "Active class folder - has samples in samples.csv"
            kept_count += 1
        else:
            decision = "[KEEP]"
            reason = "Not class_z_* and keeping all other classes per audit rule"
            kept_count += 1
        
        msg = f"{decision} {name} - {reason}"
        logger.info(msg)
        audit_report.append(msg)
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("AUDIT SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total class folders: {len(drive_classes)}")
    logger.info(f"To DELETE (class_z_*): {deleted_count}")
    logger.info(f"To KEEP: {kept_count}")
    logger.info("=" * 80)
    
    audit_report.append(f"\n[SUMMARY] Total: {len(drive_classes)}, Delete: {deleted_count}, Keep: {kept_count}")
    
    # Write report to file
    report_path = Path(__file__).parent / 'DRIVE_AUDIT_REPORT.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(audit_report))
    
    logger.info(f"\nAudit report saved to: {report_path}")
    
    return {
        'total': len(drive_classes),
        'to_delete': deleted_count,
        'to_keep': kept_count,
        'report_path': str(report_path)
    }


if __name__ == '__main__':
    result = audit_drive_files()
    if result:
        print(f"\n✓ Audit complete: {result['to_delete']} files to delete, {result['to_keep']} to keep")
        print(f"  Report: {result['report_path']}")
