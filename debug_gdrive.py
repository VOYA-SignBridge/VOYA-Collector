import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from app.storage.gdrive_client import GoogleDriveClient

def debug_files():
    credentials_path = Path("gdrive") / "credentials.json"
    token_path = Path("gdrive") / "token.json"
    
    try:
        client = GoogleDriveClient(
            credentials_path=str(credentials_path),
            token_path=str(token_path)
        )
        root_id = client.resolve_folder_path("signbridge-storage", create_missing=False)
        print(f"Root ID for signbridge-storage: {root_id}")
        
        results = client.service.files().list(
            q=f"'{root_id}' in parents and trashed=false",
            fields="files(id, name)"
        ).execute()
        files = results.get("files", [])
        
        print(f"Found {len(files)} files:")
        for f in files:
            print(f"- {f['name']} (ID: {f['id']})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    debug_files()
