import io
import json
import logging
import os
import pickle
import shutil
import tempfile
import threading
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Dict, Iterable, List, Optional, Union
import httplib2
from google_auth_httplib2 import AuthorizedHttp
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
]


def _apply_suffix_to_filename(filename: str, suffix: str) -> str:
    suffix = (suffix or "").strip()
    if not suffix:
        return filename

    path = Path(filename)
    if path.stem.endswith(suffix):
        return filename

    if path.suffix:
        return f"{path.stem}{suffix}{path.suffix}"
    return f"{filename}{suffix}"


def apply_gdrive_suffix_to_remote_path(remote_path: str) -> str:
    """Apply the temporary Google Drive filename suffix to the final path segment only.

    Intended for catalog snapshot files such as labels.csv/samples.csv.
    """
    raw = str(remote_path or "").strip()
    if not raw:
        return raw

    path = PurePosixPath(raw.replace("\\", "/"))
    suffix = getattr(settings, "gdrive_filename_suffix", "")
    return path.with_name(_apply_suffix_to_filename(path.name, suffix)).as_posix()


class _NoRedirectHttp(httplib2.Http):
    """Let googleapiclient handle Drive upload status codes itself.

    Google Drive resumable uploads use HTTP 308 as "resume incomplete".
    Recent httplib2 versions can treat a 308 without a Location header as a
    redirect error before googleapiclient sees it.
    """

    def request(
        self,
        uri,
        method="GET",
        body=None,
        headers=None,
        redirections=0,
        connection_type=None,
    ):
        return super().request(
            uri,
            method=method,
            body=body,
            headers=headers,
            redirections=0,
            connection_type=connection_type,
        )


class GoogleDriveClient:
    def __init__(self, credentials_path: str, 
                 token_path: str,
                 root_folder_id: Optional[str] = None,
                 timeout_seconds: int = 120,
                 num_retries: int = 5,
                 chunk_mb: int = 8,
                 simple_upload_threshold_mb: int = 64):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.root_folder_id = root_folder_id
        self.timeout_seconds = max(30, int(timeout_seconds or 120))
        self.num_retries = max(0, int(num_retries or 0))
        self.chunk_size_bytes = max(1, int(chunk_mb or 1)) * 1024 * 1024
        self.simple_upload_threshold_bytes = max(0, int(simple_upload_threshold_mb or 0)) * 1024 * 1024
        self._request_lock = threading.RLock()
        self.creds = None
        self._sheets_service = None
        self.service = None
        self._authenticate()
        self.root_folder_id = self._resolve_root_folder(root_folder_id)

    def _has_required_scopes(self, creds: Credentials) -> bool:
        current_scopes = set(str(scope) for scope in (creds.scopes or []))
        required_scopes = set(SCOPES)
        return required_scopes.issubset(current_scopes)

    def _save_token_json(self, creds: Credentials) -> None:
        with open(self.token_path, 'w', encoding='utf-8') as token:
            json.dump({
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'id_token': creds.id_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': getattr(creds, 'client_secret', None),
                'scopes': list(creds.scopes) if creds.scopes else SCOPES,
            }, token, indent=2)

    def _load_token_credentials(self) -> Optional[Credentials]:
        if not os.path.exists(self.token_path):
            return None

        # Prefer JSON credentials saved by the current backend.
        try:
            with open(self.token_path, 'r', encoding='utf-8') as token:
                creds_data = json.load(token)
            if isinstance(creds_data, dict) and 'token' in creds_data:
                creds = Credentials(
                    token=creds_data['token'],
                    refresh_token=creds_data.get('refresh_token'),
                    id_token=creds_data.get('id_token'),
                    token_uri=creds_data.get('token_uri'),
                    client_id=creds_data.get('client_id'),
                    client_secret=creds_data.get('client_secret'),
                    scopes=creds_data.get('scopes', SCOPES),
                )
                logger.info("[GDrive] Loaded existing credentials from token.json")
                if self._has_required_scopes(creds):
                    return creds
                logger.info(
                    "[GDrive] Existing token scopes=%s do not include required upload scopes=%s",
                    sorted(str(scope) for scope in (creds.scopes or [])),
                    SCOPES,
                )
                return None
        except UnicodeDecodeError as e:
            logger.warning("[GDrive] Token file is not UTF-8 JSON; trying legacy pickle format: %s", e)
        except Exception as e:
            logger.warning("[GDrive] Failed to load JSON token: %s; trying legacy pickle format", e)

        # Legacy support: some previous runs may have saved a pickled Credentials object.
        try:
            with open(self.token_path, 'rb') as token:
                loaded = pickle.load(token)
            if isinstance(loaded, Credentials):
                logger.info("[GDrive] Loaded legacy pickled credentials from token file")
                if self._has_required_scopes(loaded):
                    try:
                        self._save_token_json(loaded)
                    except Exception as save_exc:
                        logger.warning("[GDrive] Could not normalize legacy token to JSON: %s", save_exc)
                    return loaded
                logger.info(
                    "[GDrive] Legacy pickled token scopes=%s do not include required upload scopes=%s",
                    sorted(str(scope) for scope in (loaded.scopes or [])),
                    SCOPES,
                )
                return None
            if isinstance(loaded, dict) and 'token' in loaded:
                creds = Credentials(
                    token=loaded['token'],
                    refresh_token=loaded.get('refresh_token'),
                    id_token=loaded.get('id_token'),
                    token_uri=loaded.get('token_uri'),
                    client_id=loaded.get('client_id'),
                    client_secret=loaded.get('client_secret'),
                    scopes=loaded.get('scopes', SCOPES),
                )
                logger.info("[GDrive] Loaded legacy pickled token payload")
                if self._has_required_scopes(creds):
                    try:
                        self._save_token_json(creds)
                    except Exception as save_exc:
                        logger.warning("[GDrive] Could not normalize legacy token payload to JSON: %s", save_exc)
                    return creds
                logger.info(
                    "[GDrive] Legacy pickled token payload scopes=%s do not include required upload scopes=%s",
                    sorted(str(scope) for scope in (creds.scopes or [])),
                    SCOPES,
                )
        except Exception as e:
            logger.warning("[GDrive] Failed to load legacy pickled token: %s", e)

        return None

    def _authenticate(self):
        """Authenticate and create Google Drive service."""
        creds = self._load_token_credentials()
        
        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                logger.info("[GDrive] Refreshed expired credentials")
                try:
                    self._save_token_json(creds)
                except Exception as save_exc:
                    logger.warning("[GDrive] Could not persist refreshed token: %s", save_exc)
            else:
                raise RuntimeError(
                    f"No usable Google Drive token found at {self.token_path}. "
                    f"Provide a token with upload scopes {SCOPES} or re-authenticate with an account that can write to Drive."
                )

        try:
            self._save_token_json(creds)
        except Exception as save_exc:
            logger.warning("[GDrive] Could not persist token JSON: %s", save_exc)

        self.creds = creds
        
        authed_http = AuthorizedHttp(
            creds,
            http=_NoRedirectHttp(timeout=self.timeout_seconds),
        )
        self.service = build('drive', 'v3', http=authed_http, cache_discovery=False)
        logger.info("[GDrive] Service initialized")

    def get_sheets_service(self):
        if self.creds is None:
            raise RuntimeError("Google Drive credentials are not initialized")
        if self._sheets_service is None:
            authed_http = AuthorizedHttp(
                self.creds,
                http=_NoRedirectHttp(timeout=self.timeout_seconds),
            )
            self._sheets_service = build('sheets', 'v4', http=authed_http, cache_discovery=False)
            logger.info("[GDrive] Sheets service initialized")
        return self._sheets_service

    def get_sheet_title(self, spreadsheet_id: str, sheet_gid: int) -> str:
        with self._request_lock:
            service = self.get_sheets_service()
            meta = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields="sheets(properties(sheetId,title))",
            ).execute(num_retries=self.num_retries)
            for sheet in meta.get("sheets", []):
                props = sheet.get("properties", {}) if isinstance(sheet, dict) else {}
                try:
                    if int(props.get("sheetId")) == int(sheet_gid):
                        title = str(props.get("title") or "")
                        if title:
                            return title
                except Exception:
                    continue
            raise RuntimeError(f"Sheet gid {sheet_gid} not found in spreadsheet {spreadsheet_id}")

    def replace_sheet_values(self, spreadsheet_id: str, sheet_gid: int, values: List[List[Any]]) -> None:
        with self._request_lock:
            service = self.get_sheets_service()
            title = self.get_sheet_title(spreadsheet_id, sheet_gid)
            logger.info("[GSheets] replace begin: spreadsheet_id=%s sheet_gid=%s title=%s rows=%s", spreadsheet_id, sheet_gid, title, len(values))
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=title,
            ).execute(num_retries=self.num_retries)
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{title}'!A1",
                valueInputOption="RAW",
                body={"values": values},
            ).execute(num_retries=self.num_retries)
            logger.info("[GSheets] replace done: spreadsheet_id=%s sheet_gid=%s title=%s", spreadsheet_id, sheet_gid, title)

    def _resolve_root_folder(self, root_folder_id: Optional[str]) -> Optional[str]:
        """Resolve the configured Google Drive root folder ID."""
        if not root_folder_id:
            return None

        root_folder_id = root_folder_id.strip()
        if not root_folder_id or root_folder_id == "root":
            return None

        try:
            folder = self.service.files().get(
                fileId=root_folder_id,
                fields="id,name,mimeType",
            ).execute(num_retries=self.num_retries)
            if folder.get("mimeType") == "application/vnd.google-apps.folder":
                logger.info("[GDrive] Using root folder ID: %s (%s)", root_folder_id, folder.get("name"))
                return root_folder_id
            logger.warning("[GDrive] Root ID is not a folder, using Drive root: %s", root_folder_id)
            raise FileNotFoundError(f"Configured Google Drive root is not a folder: {root_folder_id}")
        except HttpError as e:
            if getattr(e, "resp", None) is not None and e.resp.status != 404:
                raise

            raise FileNotFoundError(
                f"Configured Google Drive root folder ID is not accessible or not shared: {root_folder_id}"
            ) from e

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
        ).execute(num_retries=self.num_retries)
        
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
        
        file = self.service.files().create(body=file_metadata, fields='id').execute(num_retries=self.num_retries)
        logger.info(f"[GDrive] Created folder: {folder_name} (ID: {file.get('id')})")
        return file.get('id')

    def _get_folder_id(self, folder_name: str, parent_id: str) -> Optional[str]:
        """Return a child folder ID without creating it."""
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id != 'root':
            query += f" and '{parent_id}' in parents"

        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute(num_retries=self.num_retries)
        files = results.get('files', [])
        return files[0]['id'] if files else None

    def resolve_folder_path(self, path: str, *, create_missing: bool = True) -> Optional[str]:
        """Resolve a Drive folder path relative to the configured root folder."""
        with self._request_lock:
            normalized = str(path or '').replace('\\', '/').strip('/')
            if not normalized:
                logger.debug("[GDrive] resolve_folder_path: empty path -> root")
                return self.root_folder_id or 'root'

            current_parent = self.root_folder_id or 'root'
            logger.debug(
                "[GDrive] resolve_folder_path start: path=%s create_missing=%s root=%s",
                normalized,
                create_missing,
                current_parent,
            )
            for part in [p for p in normalized.split('/') if p]:
                folder_id = self._get_folder_id(part, current_parent)
                if folder_id is None:
                    logger.debug(
                        "[GDrive] resolve_folder_path missing folder: part=%s parent=%s create_missing=%s",
                        part,
                        current_parent,
                        create_missing,
                    )
                    if not create_missing:
                        return None
                    folder_id = self._get_or_create_folder(part, current_parent)
                else:
                    logger.debug(
                        "[GDrive] resolve_folder_path found folder: part=%s parent=%s id=%s",
                        part,
                        current_parent,
                        folder_id,
                    )
                current_parent = folder_id
            logger.debug("[GDrive] resolve_folder_path done: path=%s id=%s", normalized, current_parent)
            return current_parent

    def _get_item_metadata(self, file_id: str) -> Dict[str, Any]:
        return self.service.files().get(
            fileId=file_id,
            fields='id,name,mimeType,parents',
        ).execute(num_retries=self.num_retries)

    def move_folder_path(self, source_path: str, target_path: str) -> str:
        """Move a Drive folder subtree to a new path and/or folder name."""
        with self._request_lock:
            source = PurePosixPath(str(source_path).replace('\\', '/'))
            target = PurePosixPath(str(target_path).replace('\\', '/'))

            logger.info("[GDrive] move_folder_path start: source=%s target=%s", source.as_posix(), target.as_posix())

            source_id = self.resolve_folder_path(source.as_posix(), create_missing=False)
            if not source_id:
                logger.warning("[GDrive] move_folder_path source missing: %s", source.as_posix())
                raise FileNotFoundError(f"Drive folder not found: {source.as_posix()}")

            source_meta = self._get_item_metadata(source_id)
            source_parents = source_meta.get('parents') or []
            old_parent_id = source_parents[0] if source_parents else None
            logger.debug(
                "[GDrive] move_folder_path source meta: id=%s name=%s parents=%s",
                source_id,
                source_meta.get('name'),
                source_parents,
            )

            target_parent_path = target.parent.as_posix()
            target_parent_id = self.resolve_folder_path(target_parent_path, create_missing=True)
            if target_parent_id is None:
                logger.warning("[GDrive] move_folder_path target parent missing: %s", target_parent_path)
                raise FileNotFoundError(f"Target Drive parent not found: {target_parent_path}")

            logger.debug(
                "[GDrive] move_folder_path target parent resolved: parent_path=%s parent_id=%s final_name=%s",
                target_parent_path,
                target_parent_id,
                target.name,
            )

            request_kwargs: Dict[str, Any] = {
                'fileId': source_id,
                'body': {'name': target.name},
                'fields': 'id,name,parents',
            }
            if old_parent_id and old_parent_id != target_parent_id:
                request_kwargs['addParents'] = target_parent_id
                request_kwargs['removeParents'] = old_parent_id
                logger.debug(
                    "[GDrive] move_folder_path reparenting: addParents=%s removeParents=%s",
                    target_parent_id,
                    old_parent_id,
                )
            elif not old_parent_id:
                request_kwargs['addParents'] = target_parent_id
                logger.debug("[GDrive] move_folder_path attaching orphan folder to parent=%s", target_parent_id)

            updated = self.service.files().update(**request_kwargs).execute(num_retries=self.num_retries)
            logger.info(
                "[GDrive] move_folder_path done: %s -> %s (id=%s)",
                source.as_posix(),
                target.as_posix(),
                source_id,
            )
            return updated.get('id', source_id)

    def delete_path(self, remote_path: str) -> bool:
        """Delete a Drive file or folder tree by path relative to the configured root."""
        with self._request_lock:
            logger.info("[GDrive] delete_path start: path=%s", remote_path)
            folder_id = self.resolve_folder_path(remote_path, create_missing=False)
            if not folder_id:
                logger.warning("[GDrive] delete_path skip: path not found=%s", remote_path)
                return False

            meta = self._get_item_metadata(folder_id)
            logger.debug(
                "[GDrive] delete_path resolved item: id=%s name=%s mimeType=%s parents=%s",
                folder_id,
                meta.get('name'),
                meta.get('mimeType'),
                meta.get('parents'),
            )
            self.service.files().delete(fileId=folder_id).execute(num_retries=self.num_retries)
            logger.info("[GDrive] delete_path done: path=%s id=%s", remote_path, folder_id)
            return True

    def delete_file(self, file_ref: str) -> bool:
        """Delete a Drive file by remote path, Drive URL, gdrive:// URL, or file ID."""
        with self._request_lock:
            ref = str(file_ref or "").strip()
            if not ref:
                return False

            file_id: Optional[str] = None
            if ref.startswith("gdrive://"):
                file_id = ref.replace("gdrive://", "", 1).strip() or None
            elif "drive.google.com" in ref:
                import re

                match = re.search(r"/d/([a-zA-Z0-9_-]+)", ref)
                if match:
                    file_id = match.group(1)
            elif "/" not in ref and "\\" not in ref and len(ref) >= 10:
                file_id = ref

            if file_id:
                logger.info("[GDrive] delete_file by id start: file_id=%s", file_id)
                self.service.files().delete(fileId=file_id).execute(num_retries=self.num_retries)
                logger.info("[GDrive] delete_file by id done: file_id=%s", file_id)
                return True

            remote_path = PurePosixPath(ref.replace("\\", "/").strip("/"))
            if not remote_path.name:
                return False

            folder_id = self.resolve_folder_path(remote_path.parent.as_posix(), create_missing=False)
            if not folder_id:
                logger.warning("[GDrive] delete_file skip: folder not found for %s", ref)
                return False

            file_id = self._find_file_by_name(folder_id, remote_path.name)
            if not file_id:
                logger.warning("[GDrive] delete_file skip: file not found for %s", ref)
                return False

            logger.info("[GDrive] delete_file by path start: path=%s file_id=%s", ref, file_id)
            self.service.files().delete(fileId=file_id).execute(num_retries=self.num_retries)
            logger.info("[GDrive] delete_file by path done: path=%s file_id=%s", ref, file_id)
            return True

    def upload_folder_tree(
        self,
        local_root: str,
        remote_root: str,
        *,
        content_type: str = "application/octet-stream",
        make_public: bool = True,
        replace_existing: bool = True,
    ) -> None:
        """Upload every file in a local folder tree to the matching Drive folder tree."""
        source_root = Path(local_root)
        if not source_root.exists():
            raise FileNotFoundError(f"Local folder not found: {source_root}")

        remote_root_path = PurePosixPath(str(remote_root).replace("\\", "/").strip("/"))
        logger.info(
            "[GDrive] upload_folder_tree start: local_root=%s remote_root=%s",
            source_root,
            remote_root_path.as_posix(),
        )
        if source_root.is_file():
            logger.debug("[GDrive] upload_folder_tree single file: %s", source_root)
            self.upload_file(
                str(source_root),
                remote_root_path.as_posix(),
                content_type=content_type,
                make_public=make_public,
                replace_existing=replace_existing,
            )
            return

        self.ensure_path(remote_root_path.as_posix())
        for item in sorted(source_root.rglob("*")):
            if not item.is_file():
                continue
            relative = item.relative_to(source_root).as_posix()
            remote_file_path = remote_root_path / relative
            logger.debug(
                "[GDrive] upload_folder_tree file: local=%s remote=%s",
                item,
                remote_file_path.as_posix(),
            )
            self.upload_file(
                str(item),
                remote_file_path.as_posix(),
                content_type=content_type,
                make_public=make_public,
                replace_existing=replace_existing,
            )
        logger.info(
            "[GDrive] upload_folder_tree done: local_root=%s remote_root=%s",
            source_root,
            remote_root_path.as_posix(),
        )

    def ensure_path(self, path: str) -> str:
        """Create full folder path recursively and return final folder ID."""
        with self._request_lock:
            if not path or path in ('.', '/'):
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
                    make_public: bool = True,
                    replace_existing: bool = False) -> str:
        """Upload file to Google Drive."""
        # google-api-python-client/httplib2 is not thread-safe; serialize Drive requests per client.
        with self._request_lock:
            temp_upload_path: Optional[str] = None
            try:
                # Split path into folder and filename
                remote_path = PurePosixPath(str(remote_path).replace("\\", "/"))
                folder_path = remote_path.parent.as_posix()
                filename = remote_path.name
                
                # Create folder structure and get folder ID
                folder_id = self.ensure_path(folder_path)
                
                # Prepare media from a disk-backed source for more stable tunnel/proxy uploads.
                if isinstance(file_data, str):
                    upload_path = file_data
                    file_size = os.path.getsize(upload_path)
                    logger.info(f"[GDrive] Uploading file from disk: {upload_path} ({file_size} bytes)")
                elif isinstance(file_data, bytes):
                    file_size = len(file_data)
                    fd, temp_upload_path = tempfile.mkstemp(
                        prefix="gdrive_upload_",
                        suffix=Path(filename).suffix or ".bin",
                    )
                    os.close(fd)
                    with open(temp_upload_path, "wb") as tmp:
                        tmp.write(file_data)
                    upload_path = temp_upload_path
                    logger.info(f"[GDrive] Uploading {file_size} bytes from memory via temp file")
                else:
                    fd, temp_upload_path = tempfile.mkstemp(
                        prefix="gdrive_upload_",
                        suffix=Path(filename).suffix or ".bin",
                    )
                    os.close(fd)
                    upload_path = temp_upload_path
                    file_size = 0
                    try:
                        file_data.seek(0)
                    except Exception:
                        pass
                    with open(upload_path, "wb") as tmp:
                        while True:
                            chunk = file_data.read(8 * 1024 * 1024)
                            if not chunk:
                                break
                            tmp.write(chunk)
                            file_size += len(chunk)
                    logger.info(f"[GDrive] Uploading from stream via temp file: {file_size} bytes")

                use_resumable = (
                    self.simple_upload_threshold_bytes <= 0
                    or file_size > self.simple_upload_threshold_bytes
                )
                logger.info(
                    "[GDrive] Upload mode for %s: %s (threshold=%s bytes)",
                    filename,
                    "resumable" if use_resumable else "simple",
                    self.simple_upload_threshold_bytes,
                )
                if use_resumable:
                    media = MediaFileUpload(
                        upload_path,
                        mimetype=content_type,
                        chunksize=self.chunk_size_bytes,
                        resumable=True,
                    )
                else:
                    media = MediaFileUpload(
                        upload_path,
                        mimetype=content_type,
                        resumable=False,
                    )
                
                # Check if file already exists
                existing_file_id = self._find_file_by_name(folder_id, filename)
                if existing_file_id and replace_existing:
                    logger.info(f"[GDrive] File already exists, updating: {filename}")
                    request = self.service.files().update(
                        fileId=existing_file_id,
                        media_body=media,
                        fields='id'
                    )
                else:
                    # Upload new file
                    file_metadata = {
                        'name': filename,
                        'parents': [folder_id]
                    }
                    
                    request = self.service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    )

                if use_resumable:
                    response = None
                    while response is None:
                        status, response = request.next_chunk(num_retries=self.num_retries)
                        if status:
                            logger.debug("[GDrive] Upload progress for %s: %d%%", filename, int(status.progress() * 100))
                else:
                    response = request.execute(num_retries=self.num_retries)
                file_id = response.get('id')
                
                # Make file publicly accessible if requested
                url = None
                if make_public:
                    # Check if already has public permission
                    permissions = self.service.permissions().list(
                        fileId=file_id,
                        fields='permissions(id,type)'
                    ).execute(num_retries=self.num_retries)
                    
                    has_public = any(
                        p.get('type') == 'anyone' 
                        for p in permissions.get('permissions', [])
                    )
                    
                    if not has_public:
                        self.service.permissions().create(
                            fileId=file_id,
                            body={'type': 'anyone', 'role': 'reader'}
                        ).execute(num_retries=self.num_retries)
                        logger.info(f"[GDrive] Made file public: {filename}")
                    
                    url = f"https://drive.google.com/file/d/{file_id}/view"
                
                logger.info(f"[GDrive] Upload completed: {url or file_id}")
                return url or f"gdrive://{file_id}"
                
            except Exception as e:
                logger.error(f"[GDrive] Upload failed: {str(e)}", exc_info=True)
                raise
            finally:
                if temp_upload_path and os.path.exists(temp_upload_path):
                    try:
                        os.remove(temp_upload_path)
                    except Exception:
                        pass

    def _find_file_by_name(self, folder_id: str, filename: str) -> Optional[str]:
        """Find file by name in folder."""
        query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute(num_retries=self.num_retries)
        
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
_gdrive_client_lock = threading.Lock()


def get_gdrive_client() -> GoogleDriveClient:
    from app.config import settings

    global _gdrive_client
    if _gdrive_client is None:
        with _gdrive_client_lock:
            if _gdrive_client is None:
                credentials_path = str(settings.google_drive_credentials)
                token_path = str(settings.google_drive_token)
                root_folder = settings.google_drive_root_folder_id or None
                
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(
                        f"credentials.json not found at {credentials_path}. "
                        "Download it from Google Cloud Console."
                    )
                
                _gdrive_client = GoogleDriveClient(
                    credentials_path=credentials_path,
                    token_path=token_path,
                    root_folder_id=root_folder,
                    timeout_seconds=int(getattr(settings, "google_drive_timeout_seconds", 120)),
                    num_retries=int(getattr(settings, "google_drive_num_retries", 5)),
                    chunk_mb=int(getattr(settings, "google_drive_chunk_mb", 8)),
                    simple_upload_threshold_mb=int(getattr(settings, "google_drive_simple_upload_threshold_mb", 64)),
                )
    return _gdrive_client


def upload_to_gdrive(file_data, key: str, content_type: str = "application/octet-stream", make_public: bool = True, replace_existing: bool = False) -> str:
    """Convenience function to upload to Google Drive."""
    client = get_gdrive_client()
    return client.upload_file(file_data, key, content_type, make_public, replace_existing)


def download_from_gdrive(gdrive_url: str, local_path: Optional[str] = None) -> str:
    """Download from Google Drive to temp file or specified path."""
    if local_path is None:
        import tempfile
        fd, local_path = tempfile.mkstemp(suffix=Path(gdrive_url).suffix or '.tmp')
        os.close(fd)
    
    client = get_gdrive_client()
    return client.download_file(gdrive_url, local_path)


def materialize_sample_artifacts(
    samples: Iterable[Dict[str, Any]],
    cache_dir: Path,
    *,
    default_suffix: str = ".npz",
) -> List[Path]:
    """Resolve local or Google Drive-backed sample artifacts into local paths."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    resolved: List[Path] = []

    for idx, row in enumerate(samples):
        sample_uid = str(row.get("sample_uid") or row.get("id") or f"sample_{idx}")
        file_path = str(row.get("file_path") or "").strip()
        storage_url = str(row.get("storage_url") or "").strip()

        if file_path and Path(file_path).exists():
            resolved.append(Path(file_path))
            continue

        source = storage_url or file_path
        if not source:
            continue

        if source.startswith(("gdrive://", "https://drive.google.com")):
            target = cache_dir / f"{sample_uid}{default_suffix}"
            resolved.append(Path(download_from_gdrive(source, str(target))))
            continue

        local_source = Path(source)
        if local_source.exists():
            target = cache_dir / local_source.name
            if local_source.resolve() != target.resolve():
                shutil.copy2(local_source, target)
            resolved.append(target)

    return resolved
