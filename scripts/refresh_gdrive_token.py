#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Sequence

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _save_token(token_path: Path, creds: Credentials) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, "w", encoding="utf-8") as token_file:
        json.dump(
            {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "id_token": creds.id_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": getattr(creds, "client_secret", None),
                "scopes": list(creds.scopes) if creds.scopes else DEFAULT_SCOPES,
            },
            token_file,
            indent=2,
        )


def _parse_scopes(raw_scopes: Sequence[str] | None) -> list[str]:
    if not raw_scopes:
        return DEFAULT_SCOPES

    scopes: list[str] = []
    for value in raw_scopes:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                scopes.append(item)
    return scopes or DEFAULT_SCOPES


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh Google Drive OAuth token for VOYA-Collector")
    parser.add_argument(
        "--credentials",
        default=os.getenv("GOOGLE_DRIVE_CREDENTIALS", "gdrive/credentials.json"),
        help="Path to OAuth client credentials JSON",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GOOGLE_DRIVE_TOKEN", "gdrive/token.json"),
        help="Path to write token JSON",
    )
    parser.add_argument(
        "--root-folder-id",
        default=os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", ""),
        help="Optional Drive folder ID to verify after auth",
    )
    parser.add_argument(
        "--mode",
        choices=("local-server", "console"),
        default="local-server",
        help="Authentication mode. Use local-server on a desktop machine, or console if browser launch is unavailable.",
    )
    parser.add_argument(
        "--scope",
        dest="scopes",
        action="append",
        default=None,
        help="OAuth scope to request. Can be repeated or comma-separated. Defaults to Drive + Sheets.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Local server port for browser-based auth. 0 lets the OS pick a free port.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    credentials_path = Path(args.credentials)
    token_path = Path(args.token)
    scopes = _parse_scopes(args.scopes)

    if not credentials_path.exists():
        raise FileNotFoundError(f"OAuth credentials not found: {credentials_path}")

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)

    if args.mode == "console":
        print("Opening console-based OAuth flow.")
        print("Follow the URL in the browser, then paste the authorization code back into the terminal.")
        creds = flow.run_console()
    else:
        print("Opening browser-based OAuth flow.")
        creds = flow.run_local_server(port=args.port, open_browser=True)

    _save_token(token_path, creds)
    print(f"Saved token to {token_path}")
    print(f"Scopes: {', '.join(scopes)}")

    if args.root_folder_id:
        try:
            from app.storage.gdrive_client import GoogleDriveClient

            client = GoogleDriveClient(
                credentials_path=str(credentials_path),
                token_path=str(token_path),
                root_folder_id=args.root_folder_id,
                timeout_seconds=180,
                num_retries=3,
            )
            print(f"Verified root folder access: {client.root_folder_id}")
        except Exception as exc:
            print(f"Saved token, but root folder verification failed: {exc}")
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
