"""Chuẩn bị dữ liệu từ giao diện: hiện vật vận hành có chủ, tiến độ ghi JSON.

Port từ feature-v2 (60fd7d1), chỉnh lại cho hiện vật `operational/` có chủ tổ
chức của nhánh này. Không chạy make_splits thật ở đây — thứ được kiểm là LỆNH
được dựng đúng (chủ = tenant người bấm, sàn, phương ngữ), report đi qua đúng các
trạng thái, và route từ chối đúng chỗ.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity._web_compat import get_current_user
from app.modules.dataset import preparation_tasks as dp
import app.routers.training as tr

client = TestClient(app)
USER = {"id": "u-editor", "username": "bien", "is_admin": False, "tenant_id": "iso_a"}


@pytest.fixture
def prep_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(dp, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(dp, "SPLITS_DIR", tmp_path / "processed" / "splits")
    monkeypatch.setattr(dp, "VERSIONS_DIR", tmp_path / "processed" / "splits" / "versions")
    monkeypatch.setattr(dp, "RUNS_DIR", tmp_path / "processed" / "splits" / "prepare_runs")
    monkeypatch.setattr(dp, "MANIFEST_DIR", tmp_path / "dataset" / "manifests")
    return tmp_path


def _fake_make_splits(tmp_path, *, fail_for=()):
    """Giả lập make_splits: ghi split_metadata.json cho hiện vật được yêu cầu."""
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)

        class P:  # noqa: D401 - đủ cho _run
            returncode = 0
            stdout = "[floor] ok"
            stderr = ""

        i = cmd.index("--operational_split_id")
        split_id = cmd[i + 1]
        d = cmd[cmd.index("--dialects") + 1]
        if d in fail_for:
            P.returncode = 1
            P.stderr = f"[floor] min_samples_per_class=25: còn 1 lớp — {d} chưa đủ"
            return P
        out = tmp_path / "processed" / "splits" / "operational" / split_id
        out.mkdir(parents=True)
        (out / "split_metadata.json").write_text(json.dumps({
            "purpose": "operational", "split_id": split_id, "num_classes": 7,
            "tenant_id": cmd[cmd.index("--tenant_id") + 1],
            "policy": {"min_samples_per_class": int(cmd[cmd.index("--min_samples_per_class") + 1])},
            "classes": [{"class_uid": "x", "dialect": d}],
        }), encoding="utf-8")
        return P

    return run, calls


def test_task_builds_one_owned_artifact_per_dialect(prep_dirs, monkeypatch):
    run, calls = _fake_make_splits(prep_dirs)
    monkeypatch.setattr(dp.subprocess, "run", run)
    report = dp.prepare_dataset.run(
        "abcdef123456", tenant_id="iso_a", dialects=["hoa-de", "can-tho"],
        min_samples_per_class=25, seed=7, requested_by="bien")
    assert report["status"] == "completed"
    assert [c[c.index("--dialects") + 1] for c in calls] == ["hoa-de", "can-tho"]
    for c in calls:
        assert c[c.index("--tenant_id") + 1] == "iso_a"          # chủ = tổ chức người bấm
        assert c[c.index("--min_samples_per_class") + 1] == "25"
        assert c[c.index("--seed") + 1] == "7"
        assert "--dataset_manifest" not in c                      # đường vận hành, không đụng tệp gốc
    ids = [s["split_id"] for s in report["operational_splits"]]
    assert ids[0].startswith("hoa-de-") and ids[0].endswith("-abcdef-floor25")
    assert all(s["ok"] and s["tenant_id"] == "iso_a" for s in report["operational_splits"])
    # Report bền trên đĩa, đọc lại được.
    assert dp.read_report("abcdef123456")["status"] == "completed"


def test_task_reports_per_dialect_failure_and_keeps_the_rest(prep_dirs, monkeypatch):
    run, _ = _fake_make_splits(prep_dirs, fail_for={"can-tho"})
    monkeypatch.setattr(dp.subprocess, "run", run)
    report = dp.prepare_dataset.run(
        "abcdef123456", tenant_id="iso_a", dialects=["hoa-de", "can-tho"], min_samples_per_class=25)
    assert report["status"] == "completed"           # còn một cái dùng được
    by = {s["dialect"]: s for s in report["operational_splits"]}
    assert by["hoa-de"]["ok"] is True
    assert by["can-tho"]["ok"] is False and "chưa đủ" in by["can-tho"]["error"]
    assert any("can-tho" in w for w in report["warnings"])


def test_task_fails_when_nothing_built(prep_dirs, monkeypatch):
    run, _ = _fake_make_splits(prep_dirs, fail_for={"can-tho"})
    monkeypatch.setattr(dp.subprocess, "run", run)
    report = dp.prepare_dataset.run("abcdef123456", tenant_id="iso_a", dialects=["can-tho"])
    assert report["status"] == "failed"
    assert "không dựng được" in report["error"]


def test_read_report_rejects_path_like_ids(prep_dirs):
    assert dp.read_report("../../etc/passwd") is None
    assert dp.read_report("") is None


class TestRoute:
    @pytest.fixture(autouse=True)
    def _auth(self, monkeypatch):
        app.dependency_overrides[get_current_user] = lambda: USER
        # Huấn luyện đi theo phạm vi request (tổ chức đang làm việc), không theo
        # `tenant_id` của tài khoản; ở đây hai thứ trùng nhau.
        import app.modules.saas.tenant_middleware as tm
        monkeypatch.setattr(tm, "resolve_tenant", lambda cookie, bearer: USER["tenant_id"])
        monkeypatch.setattr(tr, "assert_can_use_dialect", lambda d, uid: None)
        # Người giả không có grant trong DB; cổng tenant không phải thứ đang kiểm.
        import app.modules.security.access_gate as gate
        monkeypatch.setattr(gate, "_has_any_tenant_grant", lambda user: True)
        yield
        app.dependency_overrides.pop(get_current_user, None)

    def test_start_writes_pending_report_and_enqueues_with_caller_tenant(self, prep_dirs, monkeypatch):
        sent = {}
        monkeypatch.setattr(dp.prepare_dataset, "delay", lambda **kw: sent.update(kw))
        r = client.post("/training/dataset/prepare", json={"dialects": ["hoa-de"], "seed": 3})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "queued" and body["dialects"] == ["hoa-de"]
        assert sent["tenant_id"] == "iso_a" and sent["dialects"] == ["hoa-de"] and sent["seed"] == 3
        assert sent["min_samples_per_class"] == body["min_samples_per_class"] > 0
        # Report "đang chờ" đã có TRƯỚC khi worker nhận việc.
        rep = dp.read_report(body["run_id"])
        assert rep["status"] == "queued" and rep["tenant_id"] == "iso_a"

    def test_start_refuses_empty_dialects(self):
        r = client.post("/training/dataset/prepare", json={"dialects": []})
        assert r.status_code == 400

    def test_get_hides_other_tenants_runs(self, prep_dirs):
        dp.create_pending_report("aaaaaa111111", tenant_id="iso_b", dialects=["x"], floor=25,
                                 seed=1, with_research=False, requested_by="ai")
        assert client.get("/training/dataset/prepare/aaaaaa111111").status_code == 404
        dp.create_pending_report("bbbbbb222222", tenant_id="iso_a", dialects=["x"], floor=25,
                                 seed=1, with_research=False, requested_by="bien")
        r = client.get("/training/dataset/prepare/bbbbbb222222")
        assert r.status_code == 200 and r.json()["status"] == "queued"


def test_research_names_carry_the_full_manifest_version_and_never_overwrite(prep_dirs, monkeypatch):
    """`alphabet_loso_v5` từng trùng tên hiện vật isds2026_v5 chép từ máy khác và
    ghi đè hai fold của nó (15/09/2026). Tên phải mang trọn `VSL2026_v5`, và thư
    mục đã có thì DỪNG chứ không ghi."""
    run, calls = _fake_make_splits(prep_dirs)
    (prep_dirs / "dataset" / "manifests").mkdir(parents=True)
    (prep_dirs / "processed" / "splits" / "make_loso_folds.py").parent.mkdir(parents=True, exist_ok=True)

    def run_all(cmd, **kw):
        if "--operational_split_id" in cmd:
            return run(cmd, **kw)

        class P:
            returncode = 0
            stdout = "[OK]"
            stderr = ""

        if "--output_version" in cmd and "--dataset_manifest" in cmd:
            out = prep_dirs / "processed" / "splits" / "versions" / cmd[cmd.index("--output_version") + 1]
            out.mkdir(parents=True, exist_ok=True)
            (out / "split_metadata.json").write_text(json.dumps({"valid_for_research": True, "num_classes": 3}), encoding="utf-8")
        calls.append(cmd)
        return P

    monkeypatch.setattr(dp.subprocess, "run", run_all)
    # Hiện vật cũ trùng số đuôi đã có sẵn — không được đụng.
    old = prep_dirs / "processed" / "splits" / "versions" / "alphabet_loso_v1" / "test_S001"
    old.mkdir(parents=True)
    (old / "train.csv").write_text("cu", encoding="utf-8")

    report = dp.prepare_dataset.run("abcdef123456", tenant_id="iso_a", dialects=["bang-chu-cai"],
                                    with_research=True, profiles=["alphabet"])
    names = [c[c.index("--output_version") + 1] for c in calls if "--output_version" in c]
    assert "alphabet_strict_VSL2026_v1" in names
    assert not any(n == "alphabet_strict_v1" or n == "alphabet_loso_v1" for n in names)
    assert (old / "train.csv").read_text(encoding="utf-8") == "cu"
    assert report["research_splits"][0]["split_version"] == "alphabet_strict_VSL2026_v1"
