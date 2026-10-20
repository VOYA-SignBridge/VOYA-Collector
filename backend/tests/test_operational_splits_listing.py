"""GET /training/splits/operational — hiện vật vận hành mà tổ chức mình ghim được.

Bước Chia Tập của giao diện chọn từ danh sách này. Nó phải lọc qua CHÍNH bộ
phân giải: hiện vật không chủ (hai hiện vật 15/08 còn trên đĩa) và hiện vật của
tổ chức khác không được liệt kê — liệt kê rồi mới bị từ chối lúc "Bắt đầu" là
bắt người dùng đoán lần nữa.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user
import app.routers.training as tr

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from processed.train_utils.split_artifact import file_hashes, owner_binding  # noqa: E402

client = TestClient(app)
COT = "sample_uid,class_uid,slug,dialect,region,target_idx\n"


def _artifact(root: Path, split_id: str, *, tenant_id, dialect="hoa-de", generated_at="2026-09-14T00:00:00+00:00"):
    d = root / "operational" / split_id
    d.mkdir(parents=True)
    for ten, n in (("train", 3), ("val", 1), ("test", 1)):
        d.joinpath(f"{ten}.csv").write_text(
            COT + "".join(f"s-{ten}-{i},UID_A,an,{dialect},bac,0\n" for i in range(n)), encoding="utf-8")
    files = file_hashes(d)
    meta = {
        "purpose": "operational", "split_id": split_id, "files": files,
        "classes": [{"class_uid": "UID_A", "target_idx": 0, "dialect": dialect}],
        "num_classes": 1, "policy": {"min_samples_per_class": 25},
        "generated_at": generated_at, "split_mode": "sample",
    }
    if tenant_id is not None:
        meta["tenant_id"] = tenant_id
        meta["owner_binding"] = owner_binding(split_id=split_id, tenant_id=tenant_id, files=files)
    d.joinpath("split_metadata.json").write_text(json.dumps(meta), encoding="utf-8")


@pytest.fixture
def splits_root(tmp_path, monkeypatch):
    _artifact(tmp_path, "hoa-de-cu", tenant_id="iso_a", generated_at="2026-09-01T00:00:00+00:00")
    _artifact(tmp_path, "hoa-de-moi", tenant_id="iso_a", generated_at="2026-09-14T00:00:00+00:00")
    _artifact(tmp_path, "hoa-de-vo-chu", tenant_id=None)
    _artifact(tmp_path, "hoa-de-cua-b", tenant_id="iso_b")
    monkeypatch.setattr(tr, "SPLITS_DIR", tmp_path)
    return tmp_path


def _as(tenant, monkeypatch):
    """Người dùng làm việc ở chính tổ chức nhà: tài khoản VÀ phạm vi request.

    Danh sách đi theo phạm vi request (tổ chức đang làm việc) từ 18/10/2026,
    không theo `tenant_id` của tài khoản — xem test_training_working_tenant.py.
    """
    import app.modules.saas.tenant_middleware as tm

    monkeypatch.setattr(tm, "resolve_tenant", lambda cookie, bearer: tenant)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1", "username": "x", "is_admin": False, "tenant_id": tenant}


def test_lists_only_owned_resolvable_artifacts_newest_first(splits_root, monkeypatch):
    _as("iso_a", monkeypatch)
    try:
        r = client.get("/training/splits/operational")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 200, r.text
    ids = [x["split_id"] for x in r.json()]
    assert ids == ["hoa-de-moi", "hoa-de-cu"]
    first = r.json()[0]
    assert first["dialects"] == ["hoa-de"]
    assert first["counts"] == {"train": 3, "val": 1, "test": 1}
    assert first["min_samples_per_class"] == 25


def test_other_tenant_sees_only_its_own(splits_root, monkeypatch):
    _as("iso_b", monkeypatch)
    try:
        r = client.get("/training/splits/operational")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert [x["split_id"] for x in r.json()] == ["hoa-de-cua-b"]
