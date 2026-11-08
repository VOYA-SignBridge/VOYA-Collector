"""Read-only, incremental export of the application's Google Drive tree.

Runs INSIDE the backend image (the only place the Google client libraries are
installed): `python /workspace/scripts/ops/drive_export.py /export`. Nothing on
Drive is created, moved or deleted, and a refreshed OAuth token stays in memory
so the live token.json is never rewritten by a backup.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

FOLDER = "application/vnd.google-apps.folder"
SHORTCUT = "application/vnd.google-apps.shortcut"
OFFICE = "application/vnd.openxmlformats-officedocument."
# Google-native files have no bytes to download; export them to open formats.
EXPORTS = {
    "application/vnd.google-apps.spreadsheet": (OFFICE + "spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.document": (OFFICE + "wordprocessingml.document", ".docx"),
    "application/vnd.google-apps.presentation": (OFFICE + "presentationml.presentation", ".pptx"),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
}
FIELDS = "id,name,mimeType,size,md5Checksum,modifiedTime,parents,shortcutDetails"


def credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token = Path(os.getenv("GOOGLE_DRIVE_TOKEN") or "gdrive/token.json")
    if not token.is_absolute():
        token = Path("/workspace") / token
    try:
        info = json.loads(token.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Drive token is missing or not JSON ({token.name}): {exc.__class__.__name__}")
    creds = Credentials.from_authorized_user_info(info)
    if not creds.valid:
        creds.refresh(Request())
    return creds


def suffix(name):
    return Path(name).suffix[:16] if Path(name).suffix.isascii() else ""


def stored_name(item):
    # Stored by FILE ID: Drive allows duplicate and Windows-illegal names, and
    # the file ID is what the database and the inventory refer to.
    export = EXPORTS.get(item["mimeType"])
    return "files/" + item["id"] + (export[1] if export else suffix(item["name"]))


def md5(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "md5").hexdigest()


def walk(service, root_id):
    """Every folder/file under root, plus shortcut targets outside the tree."""
    folders, files, seen, queue = [], [], {root_id}, [(root_id, "")]
    while queue:
        parent, prefix = queue.pop()
        token = None
        while True:
            page = service.files().list(
                q=f"'{parent}' in parents and trashed=false", pageSize=1000, pageToken=token,
                fields=f"nextPageToken,files({FIELDS})", supportsAllDrives=True,
                includeItemsFromAllDrives=True).execute()
            for item in page.get("files", []):
                item["path"] = f"{prefix}/{item['name']}" if prefix else item["name"]
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                if item["mimeType"] == FOLDER:
                    folders.append(item)
                    queue.append((item["id"], item["path"]))
                    continue
                files.append(item)
                target = (item.get("shortcutDetails") or {}).get("targetId")
                if item["mimeType"] == SHORTCUT and target and target not in seen:
                    seen.add(target)
                    linked = service.files().get(fileId=target, fields=FIELDS,
                                                 supportsAllDrives=True).execute()
                    linked["path"] = f"(shortcut target)/{item['path']}"
                    (folders if linked["mimeType"] == FOLDER else files).append(linked)
                    if linked["mimeType"] == FOLDER:
                        queue.append((linked["id"], linked["path"]))
            token = page.get("nextPageToken")
            if not token:
                break
    return folders, files


def configured_ids(environ=os.environ):
    """Spreadsheets the app writes to by ID; they usually live OUTSIDE the root folder."""
    return {key: value.strip() for key, value in environ.items()
            if key.endswith("_SPREADSHEET_ID") and value.strip()}


def add_configured(service, files, errors):
    listed = {item["id"] for item in files}
    for key, file_id in sorted(configured_ids().items()):
        if file_id in listed:
            continue
        try:
            item = service.files().get(fileId=file_id, fields=FIELDS, supportsAllDrives=True).execute()
        except Exception as exc:  # Must not vanish silently: the app still writes to it.
            errors.append({"id": file_id, "path": f"({key})", "error": str(exc)[:300]})
            continue
        item["path"] = f"({key})/{item['name']}"
        files.append(item)
        listed.add(file_id)


def download(service, item, target):
    from googleapiclient.http import MediaIoBaseDownload

    export = EXPORTS.get(item["mimeType"])
    if export:
        request = service.files().export_media(fileId=item["id"], mimeType=export[0])
    else:
        request = service.files().get_media(fileId=item["id"], supportsAllDrives=True)
    partial = target.with_name(target.name + ".part")
    with partial.open("wb") as stream:
        downloader = MediaIoBaseDownload(stream, request, chunksize=32 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk(num_retries=5)
    if item.get("md5Checksum") and md5(partial) != item["md5Checksum"]:
        partial.unlink()
        raise RuntimeError("md5 mismatch after download")
    partial.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root-id", default=os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "").strip())
    args = parser.parse_args()
    if not args.root_id or args.root_id == "root":
        raise SystemExit("GOOGLE_DRIVE_ROOT_FOLDER_ID is not set; refusing to export a whole My Drive.")
    from googleapiclient.discovery import build

    service = build("drive", "v3", credentials=credentials(), cache_discovery=False)
    out = args.output
    (out / "files").mkdir(parents=True, exist_ok=True)
    previous = {}
    if (out / "inventory.json").exists():
        previous = {f["id"]: f for f in json.loads((out / "inventory.json").read_text("utf-8"))["files"]}
    root = service.files().get(fileId=args.root_id, fields=FIELDS, supportsAllDrives=True).execute()
    folders, files = walk(service, args.root_id)
    errors, reused, fetched = [], 0, 0
    add_configured(service, files, errors)
    for index, item in enumerate(files, 1):
        if item["mimeType"] == SHORTCUT:
            continue  # The pointer itself has no content; its target is in `files`.
        item["stored"] = stored_name(item)
        target = out / item["stored"]
        old = previous.get(item["id"])
        if (old and target.is_file() and old.get("modifiedTime") == item.get("modifiedTime")
                and old.get("md5Checksum") == item.get("md5Checksum")):
            reused += 1
            continue
        try:
            download(service, item, target)
            fetched += 1
        except Exception as exc:  # Keep going: report EVERY missing file, then fail.
            item.pop("stored")
            errors.append({"id": item["id"], "path": item["path"], "error": str(exc)[:300]})
        if index % 200 == 0:
            print(f"  Drive: {index}/{len(files)} checked", flush=True)
    # A failed download keeps its previous copy on disk (the run still fails),
    # so only names that no longer belong to ANY listed file are stale.
    known = {stored_name(item) for item in files if item["mimeType"] != SHORTCUT}
    stale = [p for p in (out / "files").iterdir() if f"files/{p.name}" not in known]
    for path in stale:
        path.unlink()  # Deleted on Drive since the last sync, or a dead .part file.
    inventory = {"format": 1, "exported_at": datetime.now(timezone.utc).isoformat(),
                 "root": {"id": root["id"], "name": root["name"]}, "folders": folders, "files": files,
                 "errors": errors, "bytes": sum(int(f.get("size") or 0) for f in files)}
    # Written LAST and atomically: a crashed run never leaves a valid-looking inventory.
    (out / "inventory.json.tmp").write_text(json.dumps(inventory, ensure_ascii=False, indent=1), "utf-8")
    (out / "inventory.json.tmp").replace(out / "inventory.json")
    print(f"Drive export: {len(folders)} folders, {len(files)} files "
          f"({fetched} downloaded, {reused} unchanged), {len(errors)} errors.")
    if errors:
        for error in errors[:20]:
            # stdout, not stderr: the pack captures stderr (it may hold credentials).
            print(f"  FAILED {error['path']}: {error['error']}", flush=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
