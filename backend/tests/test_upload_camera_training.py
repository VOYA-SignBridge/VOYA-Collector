"""Contract tests for the media pipeline: video upload, live-capture (camera),
on-demand processing, and the training lifecycle incl. model promote/export.

These exercise the ROUTES + auth/CSRF + input validation + the pure data-shaping
logic (landmark -> 126-dim sequence), and the real DB queries for training-job
persistence. The genuinely heavy parts are mocked at the seam:
  - Celery dispatch (video processing / training / gdrive) -> no worker needed
  - file writes + npz save + class registration -> no disk/dataset side effects
  - torch checkpoint load -> not needed for the promote GUARD paths

So the real MediaPipe feature extraction and GPU training aren't run here (they
belong to the manual/integration flow); everything AROUND them — the API
surface, validation, idempotency, routing, and DB — is covered.

Requires postgres + redis up (conftest points them at localhost).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app
from app.storage.metadata_db import _execute, _fetch_all

PW = "PipePass12!"


def _ip():
    import random
    return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _make_client(is_admin=False):
    uid = uuid.uuid4().hex[:8]
    u = auth.create_user(username=f"pipe_{uid}", email=f"pipe_{uid}@example.com",
                         password=PW, is_admin=is_admin)
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"identifier": u["username"], "password": PW},
               headers={"X-Forwarded-For": _ip()})
    assert r.status_code == 200, r.text
    return c, u


def _csrf(c):
    return {"X-CSRF-Token": c.cookies.get("voya_csrf", ""), "X-Forwarded-For": _ip()}


@pytest.fixture
def user_client():
    c, u = _make_client(is_admin=False)
    yield c, u
    c.cookies.clear()
    _execute("DELETE FROM users WHERE id = %s", (u["id"],))


@pytest.fixture
def admin_client():
    c, u = _make_client(is_admin=True)
    yield c, u
    c.cookies.clear()
    _execute("DELETE FROM users WHERE id = %s", (u["id"],))


def _fake_class():
    # folder_name() is a METHOD on the real class_meta, not an attribute.
    return SimpleNamespace(
        class_uid="SOTTEST_cls", slug="test-slug", label_original="xin chào",
        language="vn", dialect="common", class_idx=1, folder_name=lambda: "class_test",
    )


# ===========================================================================
# auth + CSRF gates (route protection)
# ===========================================================================

def test_upload_endpoints_require_authentication():
    anon = TestClient(app)
    assert anon.post("/api/v1/upload/camera", json={"frames": []}).status_code == 401
    assert anon.post("/api/v1/training/start", json={}).status_code == 401


def test_state_changing_calls_require_csrf(user_client):
    c, _ = user_client
    # logged in but NO X-CSRF-Token header → blocked by the csrf middleware.
    r = c.post("/api/v1/training/start", json={}, headers={"X-Forwarded-For": _ip()})
    assert r.status_code == 403
    assert "CSRF" in r.json()["detail"]


# ===========================================================================
# video upload
# ===========================================================================

def _post_video(c, *, label="xin chào", upload_uid=None, extra=None):
    data = {"label": label, "language": "vn", "dialect": "common"}
    if upload_uid:
        data["upload_uid"] = upload_uid
    if extra:
        data.update(extra)
    return c.post("/api/v1/upload/video",
                  files={"file": ("clip.mp4", b"\x00\x01\x02fake-mp4-bytes", "video/mp4")},
                  data=data, headers=_csrf(c))


def test_video_upload_stores_raw_and_returns_uid(user_client):
    c, _ = user_client
    captured = {}
    with patch("app.routers.upload.get_or_register_class", return_value=_fake_class()), \
         patch("app.routers.upload.save_upload_with_limit", return_value=(17, "/dataset/raw/clip.mp4")), \
         patch("app.routers.upload.append_raw_upload_row", side_effect=lambda row: captured.update(row)), \
         patch("app.storage.metadata_db.insert_raw_upload") as ins, \
         patch("app.routers.upload.find_raw_upload", return_value=None):
        r = _post_video(c)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True and body["upload_uid"]
    assert body["storage_url"] == "/dataset/raw/clip.mp4"
    # the row we persisted carries the right provenance
    assert captured["source_type"] == "video"
    assert captured["class_uid"] == "SOTTEST_cls"
    ins.assert_called_once()                       # DB insert attempted
    assert ins.call_args[0][0]["auth_user_id"]     # tied to the auth user


def test_video_upload_is_idempotent_on_upload_uid(user_client):
    c, _ = user_client
    uid = uuid.uuid4().hex  # valid 32-hex
    existing = {"upload_uid": uid, "session_id": "s1", "storage_url": "/dataset/x.mp4"}
    with patch("app.routers.upload.find_raw_upload", return_value=existing):
        r = _post_video(c, upload_uid=uid)
    assert r.status_code == 200
    body = r.json()
    assert body["duplicate"] is True
    assert body["upload_uid"] == uid


def test_video_upload_rejects_empty_label(user_client):
    c, _ = user_client
    with patch("app.routers.upload.get_or_register_class", return_value=_fake_class()):
        r = _post_video(c, label="   ")
    assert r.status_code == 422


# ===========================================================================
# on-demand processing (feature extraction dispatch)
# ===========================================================================

def _fake_task(tid="task-123"):
    m = MagicMock()
    m.delay.return_value = SimpleNamespace(id=tid)
    return m


def test_process_single_upload_uid_enqueues(user_client):
    c, _ = user_client
    uid = uuid.uuid4().hex
    row = {"upload_uid": uid, "storage_url": "/dataset/x.mp4", "label_original": "x"}
    with patch("app.routers.upload.find_raw_upload", return_value=row), \
         patch("app.tasks.enqueue_process_video", _fake_task()):
        r = c.post("/api/v1/upload/video/process", json={"upload_uid": uid}, headers=_csrf(c))
    assert r.status_code == 200
    body = r.json()
    assert body["queued"] == 1 and body["results"][0]["status"] == "queued"


def test_process_reports_invalid_and_missing_uids(user_client):
    c, _ = user_client
    with patch("app.routers.upload.find_raw_upload", return_value=None), \
         patch("app.tasks.enqueue_process_video", _fake_task()):
        r = c.post("/api/v1/upload/video/process",
                   json={"upload_uids": ["zzz", uuid.uuid4().hex]}, headers=_csrf(c))
    assert r.status_code == 200
    statuses = {x["status"] for x in r.json()["results"]}
    assert statuses == {"invalid_uid", "not_found"}


def test_process_requires_some_selector(user_client):
    c, _ = user_client
    r = c.post("/api/v1/upload/video/process", json={}, headers=_csrf(c))
    assert r.status_code == 422


def test_process_by_class_404_when_no_uploads(user_client):
    c, _ = user_client
    with patch("app.routers.upload.find_raw_uploads_by_class", return_value=[]):
        r = c.post("/api/v1/upload/video/process",
                   json={"class_uid": "nope"}, headers=_csrf(c))
    assert r.status_code == 404


# ===========================================================================
# live capture (camera) — landmark -> 126-dim sequence
# ===========================================================================

def _hand(base=0.3):
    return [{"x": base + i * 0.011, "y": base + i * 0.013, "z": i * 0.007} for i in range(21)]


def _good_frame():
    return {"landmarks": {"left_hand": _hand(0.3), "right_hand": _hand(0.4)}}


def _zero_frame():
    z = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in range(21)]
    return {"landmarks": {"left_hand": z, "right_hand": z}}


def test_camera_valid_frames_build_a_seqlen_x_126_sequence(user_client):
    c, _ = user_client
    seen = {}

    def _capture(class_meta, seq, **kw):
        seen["shape"] = seq.shape
        return "/dataset/samples/x.npz"

    with patch("app.routers.upload.get_or_register_class", return_value=_fake_class()), \
         patch("app.routers.upload.save_sequence_npz", side_effect=_capture):
        r = c.post("/api/v1/upload/camera",
                   json={"label": "xin chào", "frames": [_good_frame() for _ in range(60)]},
                   headers=_csrf(c))
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
    # normalized to (seq_len, feature_dim) = (60, 126)
    assert seen["shape"] == (60, 126)


def test_camera_missing_frames_is_rejected(user_client):
    c, _ = user_client
    r = c.post("/api/v1/upload/camera", json={"label": "x", "frames": []}, headers=_csrf(c))
    assert r.status_code == 200 and r.json()["success"] is False


def test_camera_all_zero_frames_flagged_too_many_invalid(user_client):
    c, _ = user_client
    with patch("app.routers.upload.get_or_register_class", return_value=_fake_class()), \
         patch("app.routers.upload.save_sequence_npz", return_value="/x.npz"):
        r = c.post("/api/v1/upload/camera",
                   json={"label": "x", "frames": [_zero_frame() for _ in range(60)]},
                   headers=_csrf(c))
    assert r.status_code == 200
    assert r.json()["success"] is False and "invalid" in r.json()["message"].lower()


def test_camera_too_many_frames_rejected(user_client, monkeypatch):
    c, _ = user_client
    from app.routers import upload as up
    monkeypatch.setattr(up.settings, "max_camera_frames", 5, raising=False)
    r = c.post("/api/v1/upload/camera",
               json={"label": "x", "frames": [_good_frame() for _ in range(6)]},
               headers=_csrf(c))
    assert r.status_code == 200
    assert r.json()["success"] is False and "max" in r.json()["message"].lower()


# ===========================================================================
# training start + promote (model export) — lifecycle guards
# ===========================================================================

def test_training_start_dispatches_and_persists(user_client):
    c, _ = user_client
    with patch("app.training_tasks.run_training_job", _fake_task()):
        r = c.post("/api/v1/training/start", json={"epochs": 3}, headers=_csrf(c))
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["status"] == "queued" and job["total_epochs"] == 3
    # persisted to DB (query works) — then clean up.
    rows = _fetch_all("SELECT status FROM training_jobs WHERE job_id = %s", (job["id"],))
    assert rows and rows[0]["status"] == "queued"
    _execute("DELETE FROM training_jobs WHERE job_id = %s", (job["id"],))


def test_training_start_returns_503_when_dispatch_fails(user_client):
    c, _ = user_client
    broken = MagicMock()
    broken.apply_async.side_effect = RuntimeError("redis down")
    with patch("app.training_tasks.run_training_job", broken):
        r = c.post("/api/v1/training/start", json={}, headers=_csrf(c))
    assert r.status_code == 503
    # the failed job is recorded as failed
    # (job id is not returned on 503, so just assert the error surfaced)
    assert "trainer" in r.json()["detail"].lower() or "training" in r.json()["detail"].lower()


def test_promote_unknown_job_is_404(admin_client):
    c, _ = admin_client
    r = c.post("/api/v1/training/jobs/deadbeef/promote", headers=_csrf(c))
    assert r.status_code == 404


def test_promote_requires_admin(user_client):
    c, _ = user_client  # normal user
    r = c.post("/api/v1/training/jobs/whatever/promote", headers=_csrf(c))
    assert r.status_code == 403


def test_promote_rejects_uncompleted_job(admin_client):
    c, _ = admin_client
    job_id = uuid.uuid4().hex[:8]
    # seed a queued (not completed) job straight in the DB
    from app.storage.metadata_db import upsert_training_job
    upsert_training_job({
        "job_id": job_id, "status": "queued", "model_type": "tcn", "config": {},
        "auth_user_id": None, "created_at": "2026-07-20T00:00:00", "started_at": None,
        "completed_at": None, "current_epoch": 0, "total_epochs": 1, "checkpoint_path": None,
        "test_acc": None, "test_f1": None, "error_message": None, "promoted_at": None,
    })
    try:
        r = c.post(f"/api/v1/training/jobs/{job_id}/promote", headers=_csrf(c))
        assert r.status_code == 409
    finally:
        _execute("DELETE FROM training_jobs WHERE job_id = %s", (job_id,))


def test_promote_completed_tcn_job_deploys_model(admin_client, tmp_path):
    """Real torch checkpoint through the promote flow (external side effects —
    file copy, registry write, realtime hot-swap — are mocked)."""
    import torch
    from app.storage.metadata_db import upsert_training_job

    ckpt = tmp_path / "model.pt"
    torch.save({"model_type": "TCN", "model_state_dict": {}, "num_classes": 3,
                "idx_to_label": {0: "a", 1: "b", 2: "c"}, "metrics": {"test_acc": 0.9}}, ckpt)

    c, _ = admin_client
    job_id = uuid.uuid4().hex[:8]
    upsert_training_job({
        "job_id": job_id, "status": "completed", "model_type": "tcn", "config": {},
        "auth_user_id": None, "created_at": "2026-07-20T00:00:00", "started_at": None,
        "completed_at": "2026-07-20T00:05:00", "current_epoch": 1, "total_epochs": 1,
        "checkpoint_path": str(ckpt), "test_acc": 0.9, "test_f1": 0.8,
        "error_message": None, "promoted_at": None,
    })
    try:
        with patch("app.routers.training._copy_checkpoint_to_deployment",
                   return_value=str(tmp_path / "deployed" / "model.pt")), \
             patch("app.routers.training._update_registry", return_value=True), \
             patch("app.routers.training._notify_realtime_service_reload", return_value=True), \
             patch("app.training_tasks.backup_promoted_checkpoint_task", _fake_task()):
            r = c.post(f"/api/v1/training/jobs/{job_id}/promote", headers=_csrf(c))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["model_id"] == f"training_{job_id}"
        assert body["registry_updated"] is True and body["realtime_reloaded"] is True
    finally:
        _execute("DELETE FROM training_jobs WHERE job_id = %s", (job_id,))
