import os
import sys
import csv
import logging
import io
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from app.storage.gdrive_client import GoogleDriveClient
from googleapiclient.http import MediaIoBaseDownload

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def verify_cleanup():
    credentials_path = Path("gdrive") / "credentials.json"
    token_path = Path("gdrive") / "token.json"
    
    try:
        client = GoogleDriveClient(
            credentials_path=str(credentials_path),
            token_path=str(token_path)
        )
    except Exception as e:
        logger.error(f"Failed to initialize Drive client: {e}")
        return

    # Check labels2.0 (Google Sheet)
    sheet_id = "1vzCKSNCfz2MR-56Si2Mea5woLW11oDnzFF_08nsLgH4"
    try:
        request = client.service.files().export_media(fileId=sheet_id, mimeType='text/csv')
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        
        csv_content = fh.getvalue().decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        z_rows = [r for r in rows if r.get('slug', '').lower() == 'z']
        print(f"--- labels2.0 (Google Sheet) ---")
        print(f"Total rows: {len(rows)}")
        print(f"'z' rows found: {len(z_rows)}")
    except Exception as e:
        logger.error(f"Error checking labels2.0: {e}")

    # Check samples2.0.csv
    csv_id = "1XdfXpmRsEYdmw0NfeU6bozgnXwVQ5Nha"
    try:
        request = client.service.files().get_media(fileId=csv_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        
        csv_content = fh.getvalue().decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        stale_class_uid = "99282603-3c5a-z"
        z_rows = [r for r in rows if r.get('slug', '').lower() == 'z']
        stale_rows = [r for r in rows if r.get('class_uid', '') == stale_class_uid]
        
        print(f"\n--- samples2.0.csv (CSV File) ---")
        print(f"Total rows: {len(rows)}")
        print(f"'z' rows found: {len(z_rows)}")
        print(f"Stale class_uid rows found: {len(stale_rows)}")
    except Exception as e:
        logger.error(f"Error checking samples2.0.csv: {e}")

if __name__ == '__main__':
    verify_cleanup()
