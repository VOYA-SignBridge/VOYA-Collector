"""Pytest wiring for a repository that mixes two test styles.

Most research-pipeline suites are STANDALONE scripts: pure-stdlib files with a
main() that prints PASS/FAIL and returns an exit code, runnable without pytest
inside the trainer container. Pytest collects nothing from them (they define no
test_* functions), so a plain `pytest backend/tests` silently reported success
while ~200 assertions never ran.

Fix: ignore those files during normal collection and run each one as a
subprocess from test_research_suites.py, asserting its exit code. One
`pytest backend/tests` command now covers both styles.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT, REPO_ROOT / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

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
