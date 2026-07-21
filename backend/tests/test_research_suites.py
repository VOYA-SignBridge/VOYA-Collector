"""Run every standalone research-pipeline suite under pytest.

The suites in conftest.STANDALONE_SUITES are plain scripts (no pytest
dependency) so they stay runnable inside the trainer container. Pytest cannot
collect their assertions directly, so each one is executed as a subprocess here
and its exit code becomes a pytest result. The suite's own PASS/FAIL output is
attached to the failure message.

Without this, `pytest backend/tests` would report a green run while the ~200
assertions in those files never executed.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import STANDALONE_SUITES

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]

# Suites that need artifacts which may legitimately be absent (they skip
# themselves with exit 0 when so) are still asserted on exit code — a skip is
# an exit 0, a genuine failure is exit 1.


@pytest.mark.parametrize("suite", STANDALONE_SUITES)
def test_standalone_suite(suite: str) -> None:
    path = TESTS_DIR / suite
    if not path.exists():
        pytest.skip(f"{suite} not present")

    env = {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": f"{REPO_ROOT}{';' if sys.platform == 'win32' else ':'}{REPO_ROOT / 'backend'}",
    }
    import os
    merged = dict(os.environ)
    merged.update(env)

    proc = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(REPO_ROOT),
        env=merged,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    if proc.returncode != 0:
        out = (proc.stdout or "")[-4000:]
        err = (proc.stderr or "")[-2000:]
        pytest.fail(f"{suite} exited {proc.returncode}\n--- stdout ---\n{out}\n"
                    f"--- stderr ---\n{err}")

    # Surface the assertion count so a suite that silently stops asserting is
    # visible in -v output rather than looking like a pass.
    tail = [ln for ln in (proc.stdout or "").splitlines() if "passed," in ln]
    if tail:
        print(f"{suite}: {tail[-1].strip()}")
