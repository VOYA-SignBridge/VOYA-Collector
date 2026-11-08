from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

RELOCATED_SCRIPTS = [
    "scripts/dataset/oversample_balance.py",
    "scripts/migration/cleanup_legacy_features.py",
    "scripts/migration/dialect_mapping_reclassifier.py",
    "scripts/migration/dialect_reclassifier.py",
    "scripts/migration/feature_structure_audit.py",
    "scripts/migration/global_common_promoter.py",
]


@pytest.mark.parametrize("relative_path", RELOCATED_SCRIPTS)
def test_relocated_maintenance_script_help(relative_path: str):
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / relative_path), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_balancing_logic_lives_in_dataset_domain():
    from app.modules.dataset.balancing import build_balance_plan

    assert callable(build_balance_plan)
