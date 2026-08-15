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

#: Mã thoát nghĩa là "đã bỏ qua có lý do", không phải "đã kiểm và đạt".
#:
#: Trước 14/08/2026 các suite cần hiện vật có thể vắng mặt sẽ in "SKIP:" rồi
#: `return 0`, và chú thích ở đây ghi thẳng rằng "a skip is an exit 0". Nghĩa
#: là trong bảng kết quả, một suite CHƯA KIỂM GÌ trông hệt một suite đã kiểm và
#: đạt. Đó chính là false assurance: người đọc tưởng X đang được bảo vệ.
#:
#: 77 là quy ước của automake cho "skip", chọn vì nó đã có nghĩa sẵn và không
#: đụng mã thoát nào Python tự sinh.
EXIT_SKIP = 77


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
    if proc.returncode == EXIT_SKIP:
        ly_do = [ln for ln in (proc.stdout or "").splitlines()
                 if ln.strip().startswith("SKIP")]
        pytest.skip(ly_do[-1].strip() if ly_do else f"{suite} tự báo bỏ qua")

    if proc.returncode != 0:
        out = (proc.stdout or "")[-4000:]
        err = (proc.stderr or "")[-2000:]
        pytest.fail(f"{suite} exited {proc.returncode}\n--- stdout ---\n{out}\n"
                    f"--- stderr ---\n{err}")

    # Mã thoát 0 CHƯA đủ để gọi là đạt: một suite ngừng khẳng định giữa chừng
    # cũng thoát 0. Đòi bằng chứng là nó có chạy phép kiểm nào không.
    tail = [ln for ln in (proc.stdout or "").splitlines() if "passed," in ln]
    assert tail, (
        f"{suite} thoát 0 nhưng không in dòng tổng kết nào — không có bằng "
        f"chứng phép kiểm nào đã chạy. Nếu nó cố ý không kiểm gì thì phải "
        f"thoát {EXIT_SKIP} kèm một dòng 'SKIP: ...'.\n"
        f"--- stdout ---\n{(proc.stdout or '')[-2000:]}")
    print(f"{suite}: {tail[-1].strip()}")
