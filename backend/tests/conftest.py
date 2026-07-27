"""Shared test bootstrap.

Makes a bare `pytest` on the HOST target the localhost stack (the compose
test-ports override publishes postgres:5432 + redis:6379 to localhost) and find
the repo's Google Drive credentials — so the full suite runs with NO skips and
no "forgot to export an env var" false failures.

Only fills values that are UNSET, so it never overrides the real container env
(inside docker, .env already provides postgres:/redis: hostnames + /gdrive paths)
or anything you export explicitly. On a machine without gdrive credentials, the
SOT integration tests still skip gracefully.
"""

from __future__ import annotations

import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

# 1. Infra the compose test-ports override exposes on localhost. `setdefault`
#    leaves the docker/container env (postgres:/redis:) untouched.
for _key, _val in {
    "DATABASE_URL": "postgresql://admin:admin@localhost:5432/signdb",
    "REDIS_URL": "redis://localhost:6379/0",
    "CELERY_BROKER_URL": "redis://localhost:6379/0",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
    "TTS_REDIS_URL": "redis://localhost:6379/0",
}.items():
    os.environ.setdefault(_key, _val)

# 2. Point Google Drive at the repo's gdrive/ (host absolute path) so the SOT
#    integration tests find the credentials and RUN instead of skipping. If the
#    files aren't present (e.g. CI), we leave it alone and those tests skip.
_gdrive = _REPO / "gdrive"
if (_gdrive / "credentials.json").exists():
    os.environ.setdefault("GOOGLE_DRIVE_CREDENTIALS", str(_gdrive / "credentials.json"))
if (_gdrive / "token.json").exists():
    os.environ.setdefault("GOOGLE_DRIVE_TOKEN", str(_gdrive / "token.json"))

# 2b. A real hand-sign clip for the video->npz extraction test. Point it at the
#     first clip in a known sample folder if present, so the test RUNS (no skip)
#     on the data machine and skips gracefully elsewhere.
if not os.environ.get("VOYA_TEST_VIDEO"):
    _vids = []
    for _cand in (_REPO / "sample_clips", Path("E:/CTU_ProjectOutside/Videos")):
        try:
            _vids = sorted(_cand.glob("*.mp4")) if _cand.exists() else []
        except Exception:
            _vids = []
        if _vids:
            break
    if not _vids:
        # Neither of the two locations above exists on the data machine — the
        # real uploads live under dataset/raw_videos/<lang>/<dialect>/<class>/,
        # so the extraction test skipped even where clips were present. Search
        # there too (recursively, first match wins) and keep excluding the
        # rendered skeleton previews under dataset/features/, which have no real
        # hands for MediaPipe to find and would fail the test for the wrong
        # reason.
        _raw = _REPO / "dataset" / "raw_videos"
        try:
            _vids = sorted(_raw.rglob("*.mp4"))[:1] if _raw.exists() else []
        except Exception:
            _vids = []
    if _vids:
        os.environ["VOYA_TEST_VIDEO"] = str(_vids[0])

# 3. Drive root folder id (needed so SOT publishes into the shared folder, not
#    the service account's My Drive). Read just that key out of the repo .env.
if not os.environ.get("GOOGLE_DRIVE_ROOT_FOLDER_ID"):
    _envf = _REPO / ".env"
    if _envf.exists():
        for _line in _envf.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line.startswith("GOOGLE_DRIVE_ROOT_FOLDER_ID=") and not _line.startswith("#"):
                os.environ["GOOGLE_DRIVE_ROOT_FOLDER_ID"] = _line.split("=", 1)[1].strip()
                break
