#!/usr/bin/env python
"""
Enhanced audit script with detailed debugging.
"""

import os
import sys
import csv
import logging
from pathlib import Path
from typing import Set, Dict, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.config import settings
from app.storage.gdrive_client import GoogleDriveClient

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def audit_drive_detailed():
    """Detailed audit with all items listed"""
    logger.info("=" * 80)
    logger.info("ENHANCED DRIVE AUDIT - DETAILED LISTING")
    logger.info("=" * 80)
    
    credentials_path = Path(__file__).parent / 'gdrive' / 'credentials.json'
    token_path = Path(__file__).parent / 'gdrive' / 'token.json'
    
    if not credentials_path.exists():
        logger.error(f"Credentials file not found: {credentials_path}")
        return
    
    try:
        client = GoogleDriveClient(
            credentials_path=str(credentials_path),
            token_path=str(token_path),
            root_folder_id=getattr(settings, "gdrive_root_folder_id", None)
        )
    except Exception as e:
        logger.error(f"Failed to initialize Drive client: {e}")
        return
    
    # Get hoa-de folder
    try:
        folder_id = client.resolve_folder_path('features/vn/hoa-de', create_missing=False)
        logger.info(f"Hoa-de folder ID: {folder_id}")
        
        if not folder_id:
            logger.error("Hoa-de folder not found")
            return
        
        # List ALL items
        query = f"'{folder_id}' in parents and trashed=false"
        results = client.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, mimeType)',
            pageSize=1000,
            orderBy='name'
        ).execute()
        
        items = results.get('files', [])
        logger.info(f"\n=== ALL ITEMS IN features/vn/hoa-de ({len(items)} total) ===")
        
        for item in items:
            logger.info(f"  - {item['name']:<40} (ID: {item['id']}, Type: {item.get('mimeType', 'unknown')})")
        
        # Categorize
        logger.info(f"\n=== CATEGORIZATION ===")
        csvs = [i for i in items if i['name'].endswith('.csv')]
        classes = [i for i in items if i['name'].startswith('class_')]
        others = [i for i in items if i not in csvs and i not in classes]
        
        logger.info(f"CSV files: {len(csvs)}")
        for c in csvs:
            logger.info(f"  - [KEEP] {c['name']}")
        
        logger.info(f"\nClass folders: {len(classes)}")
        delete_count = 0
        keep_count = 0
        for c in classes:
            if c['name'].startswith('class_z_'):
                logger.info(f"  - [DELETE] {c['name']} - class_z_*")
                delete_count += 1
            else:
                logger.info(f"  - [KEEP] {c['name']}")
                keep_count += 1
        
        if others:
            logger.info(f"\nOther items: {len(others)}")
            for o in others:
                logger.info(f"  - [SKIP] {o['name']}")
        
        logger.info(f"\n=== DELETION PLAN ===")
        logger.info(f"Total items: {len(items)}")
        logger.info(f"To DELETE: {delete_count}")
        logger.info(f"To KEEP: {keep_count + len(csvs)}")
        
        return {
            'total': len(items),
            'to_delete': delete_count,
            'to_keep': keep_count + len(csvs),
            'items': items
        }
        
    except Exception as e:
        logger.error(f"Error during audit: {e}", exc_info=True)


if __name__ == '__main__':
    audit_drive_detailed()
