"""Shared test bootstrap for a repository that mixes two test styles.

Two jobs, both required — this file is the merge of what the deploy line and the
research line each needed from conftest:

1. ENVIRONMENT. A bare `pytest` on the HOST targets the localhost stack (the
   compose test-ports override publishes postgres:5432 + redis:6379 to
   localhost) and finds the repo's Google Drive credentials — so the full suite
   runs with NO skips and no "forgot to export an env var" false failures.
   Only UNSET values are filled, so it never overrides the real container env
   (inside docker, .env already provides postgres:/redis: hostnames + /gdrive
   paths) or anything exported explicitly. On a machine without gdrive
   credentials the SOT integration tests still skip gracefully.

2. COLLECTION. Most research-pipeline suites are STANDALONE scripts: pure-stdlib
   files with a main() that prints PASS/FAIL and returns an exit code, runnable
   without pytest inside the trainer container. Pytest collects nothing from
   them (they define no test_* functions), so a plain `pytest backend/tests`
   silently reported success while ~200 assertions never ran. They are ignored
   during normal collection and executed as subprocesses from
   test_research_suites.py, which asserts each exit code.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
# Same path under the name the research suites import.
REPO_ROOT = _REPO

for _p in (REPO_ROOT, REPO_ROOT / "backend"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

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

# Standalone suites — executed by test_research_suites.py, not collected here.
STANDALONE_SUITES = (
    "test_augmentation_geometry.py",
    "test_frozen_artifacts.py",
    "test_manifest.py",
    "test_migration_vocab.py",
    "test_phase35_scripts.py",
    "test_profile_training_prep.py",
    "test_quality.py",
    "test_signer_disjoint_split.py",
    "test_split_safety.py",
    "test_vocabulary_v2.py",
)

collect_ignore = list(STANDALONE_SUITES)
