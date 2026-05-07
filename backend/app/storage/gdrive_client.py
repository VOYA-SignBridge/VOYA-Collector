import os
import io
import pickle
import logging
from pathlib import Path
from typing import Union, BinaryIO, Optional
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.file']


class GoogleDriveClient:
    def __init__(self, credentials_path: str, 
                 token_path: str,
                 root_folder_id: Optional[str] = None):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.root_folder_id = root_folder_id
        self.service = None
        self._authenticate()
        self.root_folder_id = self._resolve_root_folder(root_folder_id)

    def _authenticate(self):
        """Authenticate and create Google Drive service."""
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
                logger.info("[GDrive] Loaded existing credentials")
        
        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                logger.info("[GDrive] Refreshed expired credentials")
            else:
                logger.info("[GDrive] Need new authentication...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
                logger.info("[GDrive] New authentication successful")
            
            # Save credentials
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('drive', 'v3', credentials=creds)
        logger.info("[GDrive] Service initialized")

    def _resolve_root_folder(self, root_folder_id: Optional[str]) -> Optional[str]:
        """Accept either a Google Drive folder ID or a friendly root folder name."""
        if not root_folder_id:
            return None

        root_folder_id = root_folder_id.strip()
        if not root_folder_id or root_folder_id == "root":
            return None

        try:
            folder = self.service.files().get(
                fileId=root_folder_id,
                fields="id,name,mimeType",
            ).execute()
            if folder.get("mimeType") == "application/vnd.google-apps.folder":
                logger.info("[GDrive] Using root folder ID: %s (%s)", root_folder_id, folder.get("name"))
                return root_folder_id
            logger.warning("[GDrive] Root ID is not a folder, using Drive root: %s", root_folder_id)
            return None
        except HttpError as e:
            if getattr(e, "resp", None) is not None and e.resp.status != 404:
                raise

            logger.info("[GDrive] Root folder ID not found; treating value as folder name: %s", root_folder_id)
            return self._get_or_create_folder(root_folder_id, "root")

    def _get_or_create_folder(self, folder_name: str, parent_id: str) -> str:
        """Get existing folder or create new one."""
        # Search for existing folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id != 'root':
            query += f" and '{parent_id}' in parents"
        
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        
        files = results.get('files', [])
        
        if files:
            logger.debug(f"[GDrive] Found existing folder: {folder_name} (ID: {files[0]['id']})")
            return files[0]['id']
        
        # Create new folder
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id] if parent_id != 'root' else []
        }
        
        file = self.service.files().create(body=file_metadata, fields='id').execute()
        logger.info(f"[GDrive] Created folder: {folder_name} (ID: {file.get('id')})")
        return file.get('id')

    def ensure_path(self, path: str) -> str:
        """Create full folder path recursively and return final folder ID."""
        if not path or path == '/':
            return self.root_folder_id or 'root'
        
        # Start from root or configured root folder
        current_parent = self.root_folder_id or 'root'
        
        # Split path and create folders one by one
        parts = [p for p in path.strip('/').split('/') if p]
        
        for part in parts:
            current_parent = self._get_or_create_folder(part, current_parent)
        
        return current_parent

    def upload_file(self, file_data: Union[bytes, BinaryIO, str], 
                    remote_path: str, 
                    content_type: str = "application/octet-stream",
                    make_public: bool = True) -> str:
        """Upload file to Google Drive."""
        try:
            # Split path into folder and filename
            remote_path = Path(remote_path)
            folder_path = str(remote_path.parent)
            filename = remote_path.name
            
            # Create folder structure and get folder ID
            folder_id = self.ensure_path(folder_path)
            
            # Prepare media
            if isinstance(file_data, str):
                # File path
                file_size = os.path.getsize(file_data)
                media = MediaIoBaseUpload(
                    open(file_data, 'rb'),
                    mimetype=content_type,
                    chunksize=1024*1024*10,  # 10MB chunks
                    resumable=True
                )
                logger.info(f"[GDrive] Uploading file from disk: {file_data} ({file_size} bytes)")
                
            elif isinstance(file_data, bytes):
                file_size = len(file_data)
                media = MediaIoBaseUpload(
                    io.BytesIO(file_data),
                    mimetype=content_type,
                    chunksize=1024*1024*10,
                    resumable=True
                )
                logger.info(f"[GDrive] Uploading {file_size} bytes from memory")
                
            else:
                # Already a file-like object
                file_data.seek(0, 2)
                file_size = file_data.tell()
                file_data.seek(0)
                media = MediaIoBaseUpload(
                    file_data,
                    mimetype=content_type,
                    chunksize=1024*1024*10,
                    resumable=True
                )
                logger.info(f"[GDrive] Uploading from stream: {file_size} bytes")
            
            # Check if file already exists
            existing_file_id = self._find_file_by_name(folder_id, filename)
            if existing_file_id:
                logger.info(f"[GDrive] File already exists, updating: {filename}")
                file = self.service.files().update(
                    fileId=existing_file_id,
                    media_body=media,
                    fields='id'
                ).execute()
                file_id = file.get('id')
            else:
                # Upload new file
                file_metadata = {
                    'name': filename,
                    'parents': [folder_id]
                }
                
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                file_id = file.get('id')
            
            # Make file publicly accessible if requested
            url = None
            if make_public:
                # Check if already has public permission
                permissions = self.service.permissions().list(
                    fileId=file_id,
                    fields='permissions(id,type)'
                ).execute()
                
                has_public = any(
                    p.get('type') == 'anyone' 
                    for p in permissions.get('permissions', [])
                )
                
                if not has_public:
                    self.service.permissions().create(
                        fileId=file_id,
                        body={'type': 'anyone', 'role': 'reader'}
                    ).execute()
                    logger.info(f"[GDrive] Made file public: {filename}")
                
                url = f"https://drive.google.com/file/d/{file_id}/view"
            
            logger.info(f"[GDrive] Upload completed: {url or file_id}")
            return url or f"gdrive://{file_id}"
            
        except Exception as e:
            logger.error(f"[GDrive] Upload failed: {str(e)}", exc_info=True)
            raise

    def _find_file_by_name(self, folder_id: str, filename: str) -> Optional[str]:
        """Find file by name in folder."""
        query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        
        files = results.get('files', [])
        return files[0]['id'] if files else None

    def download_file(self, file_id_or_url: str, local_path: str) -> str:
        """Download file from Google Drive."""
        try:
            # Extract file ID from URL if needed
            if 'drive.google.com' in file_id_or_url:
                import re
                match = re.search(r'/d/([a-zA-Z0-9_-]+)', file_id_or_url)
                if match:
                    file_id = match.group(1)
                else:
                    raise ValueError("Invalid Google Drive URL")
            else:
                file_id = file_id_or_url
                if file_id.startswith("gdrive://"):
                    file_id = file_id.replace("gdrive://", "", 1)
            
            request = self.service.files().get_media(fileId=file_id)
            
            fh = io.FileIO(local_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request, chunksize=1024*1024*10)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"[GDrive] Download progress: {int(status.progress() * 100)}%")
            
            fh.close()
            logger.info(f"[GDrive] Downloaded to: {local_path}")
            return local_path
            
        except Exception as e:
            logger.error(f"[GDrive] Download failed: {str(e)}", exc_info=True)
            raise


# Singleton instance
_gdrive_client = None


def get_gdrive_client() -> GoogleDriveClient:
    global _gdrive_client
    if _gdrive_client is None:
        credentials_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS", "credentials.json")
        token_path = os.getenv("GOOGLE_DRIVE_TOKEN", "token.pickle")
        root_folder = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", None)
        
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(
                f"credentials.json not found at {credentials_path}. "
                "Download it from Google Cloud Console."
            )
        
        _gdrive_client = GoogleDriveClient(
            credentials_path=credentials_path,
            token_path=token_path,
            root_folder_id=root_folder
        )
    return _gdrive_client


def upload_to_gdrive(file_data, key: str, content_type: str = "application/octet-stream", make_public: bool = True) -> str:
    """Convenience function to upload to Google Drive."""
    client = get_gdrive_client()
    return client.upload_file(file_data, key, content_type, make_public)


def download_from_gdrive(gdrive_url: str, local_path: Optional[str] = None) -> str:
    """Download from Google Drive to temp file or specified path."""
    if local_path is None:
        import tempfile
        fd, local_path = tempfile.mkstemp(suffix=Path(gdrive_url).suffix or '.tmp')
        os.close(fd)
    
    client = get_gdrive_client()
    return client.download_file(gdrive_url, local_path)
